"""
Weekly K-factor proposal generation.

Implements the core proposal logic with caps, seasonal adjustments, and guardrails.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

from . import baseline, smartk, dday, risk as risk_module

logger = logging.getLogger(__name__)


class ProposalResult:
    """Container for K-factor proposal result."""

    def __init__(self, customer_fuel_id: int, customer_id: int):
        self.customer_fuel_id = customer_fuel_id
        self.customer_id = customer_id
        self.location_number = None
        self.fuel_type = None
        self.current_k_before = None
        self.proposed_k = None
        self.change_pct = None
        self.reason_code = 'PENDING'
        self.method = 'Unknown'
        self.season_target = None
        self.confidence = 'Unknown'
        self.notes = ''
        self.risk_score = 0
        self.metadata = {}

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV output."""
        return {
            'CustomerFuelID': self.customer_fuel_id,
            'CustomerID': self.customer_id,
            'LocationNumber': self.location_number,
            'FuelType': self.fuel_type,
            'CurrentKFactor_Before': self.current_k_before,
            'ProposedKFactor': self.proposed_k,
            'ChangePct': self.change_pct,
            'ReasonCode': self.reason_code,
            'Method': self.method,
            'SeasonTarget': self.season_target,
            'Confidence': self.confidence,
            'Notes': self.notes,
        }


def apply_caps(proposed_k: float,
              previous_k: float,
              data_quality: str,
              risk_score: int) -> Tuple[float, bool, str]:
    """
    Apply increase/decrease caps to proposed K-factor.

    Args:
        proposed_k: Proposed K-factor
        previous_k: Previous K-factor
        data_quality: Data quality ('High', 'Medium', 'Low')
        risk_score: Customer risk score (0-100)

    Returns:
        Tuple of (capped_k, was_capped, reason)
    """
    if previous_k <= 0:
        return proposed_k, False, ''

    change_pct = (proposed_k - previous_k) / previous_k

    # Determine caps based on data quality
    if data_quality == 'High':
        max_increase = 0.15  # 15%
        max_decrease = 0.60  # 60%
    else:
        max_increase = 0.10  # 10%
        max_decrease = 0.50  # 50%

    # For high-risk customers, be more aggressive with increases
    if risk_score >= 70 and change_pct > 0:
        max_increase = max(max_increase, min(max_increase * 1.5, 0.20))  # Allow up to 20%

    # Apply caps
    if change_pct > max_increase:
        capped_k = previous_k * (1 + max_increase)
        return capped_k, True, f'CAP_LIMIT_INCREASE_{int(max_increase*100)}PCT'
    elif change_pct < -max_decrease:
        capped_k = previous_k * (1 - max_decrease)
        return capped_k, True, f'CAP_LIMIT_DECREASE_{int(max_decrease*100)}PCT'
    else:
        return proposed_k, False, ''


def check_tank_sanity(proposed_k: float,
                     customer_fuel: pd.Series,
                     degree_days_per_delivery: float = 500) -> Tuple[bool, str]:
    """
    Check if proposed K-factor makes sense given tank size.

    Args:
        proposed_k: Proposed K-factor (gallons per degree day)
        customer_fuel: Customer fuel record
        degree_days_per_delivery: Typical degree days between deliveries

    Returns:
        Tuple of (is_sane, reason)
    """
    usable_size = customer_fuel.get('UsableSize')
    optimum_delivery = customer_fuel.get('OptimumDelivery')

    if pd.isna(usable_size) or usable_size <= 0:
        return True, ''  # Can't check without tank size

    # Estimated typical delivery
    estimated_delivery = proposed_k * degree_days_per_delivery

    # Check 1: Delivery shouldn't exceed usable tank size
    if estimated_delivery > usable_size:
        return False, 'TANK_SANITY_TOO_LARGE'

    # Check 2: Delivery shouldn't be too small (< 20% of optimum)
    if pd.notna(optimum_delivery) and optimum_delivery > 0:
        if estimated_delivery < optimum_delivery * 0.2:
            return False, 'TANK_SANITY_TOO_SMALL'

    return True, ''


def assess_data_quality(deliveries: pd.DataFrame, customer_fuel: pd.Series) -> str:
    """
    Assess overall data quality for K-factor calculation.

    Returns:
        Quality rating: 'High', 'Medium', or 'Low'
    """
    if len(deliveries) == 0:
        return 'Low'

    # Recent deliveries (last 180 days)
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=180)
    recent = deliveries[deliveries['DeliveryDate'] >= cutoff]

    # Check for fills
    if 'IsFill' in deliveries.columns:
        recent_fills = recent[recent['IsFill'] == True]
    else:
        recent_fills = recent

    fill_count = len(recent_fills)

    # Check degree day quality
    good_dday_count = 0
    if 'DDayQuality' in deliveries.columns:
        good_dday_count = (recent['DDayQuality'] == 'Good').sum()

    # High quality: ≥3 recent fills with good degree day data
    if fill_count >= 3 and good_dday_count >= 3:
        return 'High'

    # Medium quality: ≥2 recent fills or good degree day coverage
    if fill_count >= 2 or good_dday_count >= 2:
        return 'Medium'

    return 'Low'


def generate_proposal_for_customer(customer_fuel: pd.Series,
                                  deliveries: pd.DataFrame,
                                  degree_days: pd.DataFrame) -> ProposalResult:
    """
    Generate K-factor proposal for a single customer.

    Args:
        customer_fuel: Customer fuel record
        deliveries: Delivery history for this customer
        degree_days: Degree day data

    Returns:
        ProposalResult object
    """
    result = ProposalResult(
        customer_fuel['CustomerFuelID'],
        customer_fuel['CustomerID']
    )

    result.location_number = customer_fuel.get('LocationNumber', '')
    result.fuel_type = customer_fuel.get('FuelType', '')
    result.current_k_before = customer_fuel.get('CurrentK')

    # Handle missing current K
    if pd.isna(result.current_k_before) or result.current_k_before <= 0:
        result.current_k_before = customer_fuel.get('PreviousK')

    # Assess data quality
    data_quality = assess_data_quality(deliveries, customer_fuel)
    result.confidence = data_quality

    # Calculate risk score
    result.risk_score = risk_module.calculate_risk_score(
        customer_fuel, deliveries, degree_days
    )

    # Determine current season
    current_season = dday.get_current_season(pd.Timestamp.now())
    result.season_target = current_season

    # Get seasonal K target
    seasonal_k = baseline.get_seasonal_k_target(customer_fuel, current_season)

    # Check if we have sufficient data
    if len(deliveries) < 2:
        result.reason_code = 'INSUFFICIENT_DATA'
        result.notes = 'Less than 2 deliveries in history'
        result.proposed_k = result.current_k_before
        return result

    # Calculate baseline K (for fallback)
    baseline_k, baseline_conf, baseline_meta = baseline.calculate_robust_baseline_k(deliveries)
    result.metadata['baseline_k'] = baseline_k
    result.metadata['baseline_confidence'] = baseline_conf

    # Get most recent delivery
    last_delivery = deliveries.iloc[-1]

    # Calculate classical K from last delivery
    k_classical, classical_quality = baseline.calculate_classical_k(last_delivery, deliveries)
    result.metadata['k_classical'] = k_classical
    result.metadata['classical_quality'] = classical_quality

    # Determine if we should use SmartK
    use_smartk, smartk_reason, smartk_conf = smartk.should_use_smartk(
        customer_fuel, deliveries
    )

    k_proposed = None
    method = 'Classical'

    if use_smartk and k_classical is not None:
        # SmartK eligible - blend
        k_smartk, smartk_forecast_conf = smartk.estimate_smartk_forecast(
            deliveries, customer_fuel, current_season
        )

        if k_smartk is not None:
            k_proposed, blend_weight = smartk.blend_smartk_with_classical(
                k_classical, k_smartk, smartk_conf
            )
            method = 'SmartKBlend'
            result.metadata['smartk_k'] = k_smartk
            result.metadata['smartk_weight'] = blend_weight
        else:
            # SmartK failed, fall back to classical
            k_proposed = k_classical
            method = 'Classical'
    elif k_classical is not None:
        # Use classical K
        k_proposed = k_classical
        method = 'Classical'
    elif baseline_k is not None:
        # No recent delivery, drift toward baseline
        if result.current_k_before and result.current_k_before > 0:
            k_proposed = baseline.drift_toward_baseline(
                result.current_k_before, baseline_k, max_drift=0.05
            )
            method = 'BaselineDrift'
        else:
            k_proposed = baseline_k
            method = 'Baseline'
    else:
        # Insufficient data
        result.reason_code = 'INSUFFICIENT_DATA'
        result.notes = 'Cannot calculate K-factor from available data'
        result.proposed_k = result.current_k_before
        return result

    result.method = method

    # Apply seasonal adjustment if applicable
    if seasonal_k and abs(seasonal_k - k_proposed) / k_proposed > 0.15:
        k_adjusted, seasonal_adj_pct = baseline.calculate_seasonal_adjustment(
            k_proposed, seasonal_k, max_adjustment=0.10
        )

        if abs(seasonal_adj_pct) > 0.01:  # Meaningful adjustment
            k_proposed = k_adjusted
            result.reason_code = 'SEASONAL_NUDGE'
            result.metadata['seasonal_adjustment_pct'] = seasonal_adj_pct

    # Determine previous K for caps
    previous_k = result.current_k_before if result.current_k_before and result.current_k_before > 0 else baseline_k

    if previous_k and previous_k > 0:
        # Apply caps
        k_capped, was_capped, cap_reason = apply_caps(
            k_proposed, previous_k, data_quality, result.risk_score
        )

        if was_capped:
            result.metadata['uncapped_k'] = k_proposed
            k_proposed = k_capped
            result.reason_code = cap_reason

        # Check tank sanity
        is_sane, sanity_reason = check_tank_sanity(k_proposed, customer_fuel)

        if not is_sane:
            # Back off to current K
            result.reason_code = sanity_reason
            result.notes = f'Proposed K fails tank sanity check: {sanity_reason}'
            k_proposed = result.current_k_before if result.current_k_before else previous_k

        # Calculate change percentage
        result.change_pct = (k_proposed - previous_k) / previous_k * 100

        # Adjust for runout risk
        if result.risk_score >= 70 and result.change_pct < 0:
            # High risk customer - don't decrease K
            result.notes = 'Decrease rejected due to high runout risk'
            result.reason_code = 'HIGH_RISK_NO_DECREASE'
            k_proposed = previous_k
            result.change_pct = 0

    else:
        # No previous K reference
        result.change_pct = None

    # Reduce allowed change if data quality is low
    if data_quality == 'Low' and result.change_pct is not None:
        if abs(result.change_pct) > 5:  # More than 5% change
            # Cut change in half
            k_proposed = previous_k * (1 + result.change_pct / 100 / 2)
            result.change_pct = result.change_pct / 2
            result.confidence = 'Low'
            if not result.notes:
                result.notes = 'Change reduced due to low data quality'

    result.proposed_k = k_proposed

    # Set default reason code if not set
    if result.reason_code == 'PENDING':
        if result.change_pct is not None and abs(result.change_pct) < 1:
            result.reason_code = 'NO_CHANGE'
        else:
            result.reason_code = 'NORMAL_UPDATE'

    return result


def generate_proposals(customer_fuel: pd.DataFrame,
                      delivery_tickets: pd.DataFrame,
                      degree_days: pd.DataFrame) -> pd.DataFrame:
    """
    Generate K-factor proposals for all customers.

    Args:
        customer_fuel: Customer fuel records
        delivery_tickets: Delivery ticket history
        degree_days: Degree day values

    Returns:
        DataFrame with proposals
    """
    logger.info("Generating K-factor proposals")

    # Calculate degree days for all deliveries first
    logger.info("Calculating degree days for deliveries...")
    delivery_tickets = dday.calculate_delivery_ddays(
        delivery_tickets, degree_days, customer_fuel
    )

    proposals = []
    total = len(customer_fuel)
    processed = 0
    skipped = 0

    # Filter to automatic delivery customers if flag exists
    if 'AutoDelivery' in customer_fuel.columns:
        auto_customers = customer_fuel[customer_fuel['AutoDelivery'] == True]
        logger.info(f"Processing {len(auto_customers)} automatic delivery customers")
    else:
        auto_customers = customer_fuel
        logger.info(f"Processing all {len(auto_customers)} customers (AutoDelivery flag not found)")

    for idx, customer in auto_customers.iterrows():
        customer_fuel_id = customer['CustomerFuelID']

        # Get deliveries for this customer
        cust_deliveries = delivery_tickets[
            delivery_tickets['CustomerFuelID'] == customer_fuel_id
        ].copy()

        # Generate proposal
        try:
            proposal = generate_proposal_for_customer(customer, cust_deliveries, degree_days)
            proposals.append(proposal.to_dict())
            processed += 1

            if proposal.reason_code in ['INSUFFICIENT_DATA', 'TANK_SANITY_TOO_LARGE', 'TANK_SANITY_TOO_SMALL']:
                skipped += 1

            if processed % 100 == 0:
                logger.info(f"Processed {processed}/{len(auto_customers)} customers")

        except Exception as e:
            logger.error(f"Error processing customer {customer_fuel_id}: {e}", exc_info=True)
            # Create error proposal
            error_proposal = ProposalResult(customer_fuel_id, customer.get('CustomerID', ''))
            error_proposal.reason_code = 'ERROR'
            error_proposal.notes = str(e)
            proposals.append(error_proposal.to_dict())
            skipped += 1

    logger.info(f"Proposal generation complete: {processed} processed, {skipped} skipped/errors")

    # Convert to DataFrame
    proposals_df = pd.DataFrame(proposals)

    # Calculate coverage
    coverage_pct = (processed - skipped) / processed * 100 if processed > 0 else 0
    logger.info(f"Coverage: {coverage_pct:.1f}%")

    return proposals_df
