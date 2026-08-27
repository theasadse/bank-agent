from typing import Dict, Any, List, Optional
from backend.models import TaxCalculateRequest, TaxCalculateResponse

class BankFeeCalculator:
    """
    Precision banking fee, surcharge, FED/VAT, and Withholding Tax calculation engine.
    Produces both numeric totals and transparent, step-by-step mathematical explanations.
    """

    @staticmethod
    def calculate(req: TaxCalculateRequest) -> TaxCalculateResponse:
        base_fee = float(req.base_fee)
        fed_rate = float(req.fed_rate or 16.0)
        intl_rate = float(req.intl_markup_rate or 0.0)
        wht_rate = float(req.wht_rate or 0.0)
        tx_amount = float(req.transaction_amount or 0.0)

        # 1. Base Fee
        # 2. FED/VAT calculation: FED applies on the service base fee
        fed_amount = round((base_fee * (fed_rate / 100.0)), 2) if fed_rate > 0 else 0.0

        # 3. International markup: applies on foreign transaction volume if applicable
        intl_amount = 0.0
        if intl_rate > 0 and tx_amount > 0:
            intl_amount = round((tx_amount * (intl_rate / 100.0)), 2)

        # 4. Withholding Tax: applies on transaction amount (e.g., cash withdrawal) or service
        wht_amount = 0.0
        if wht_rate > 0:
            target_val = tx_amount if tx_amount > 0 else base_fee
            wht_amount = round((target_val * (wht_rate / 100.0)), 2)

        total_fee = round(base_fee + fed_amount + intl_amount + wht_amount, 2)

        # Build clear mathematical step breakdown
        breakdown = []
        breakdown.append(f"1. Base Service Fee: Rs. {base_fee:,.2f}")
        
        if fed_rate > 0:
            breakdown.append(
                f"2. Provincial Sales Tax / FED ({fed_rate}% of Base Fee): "
                f"({fed_rate}/100) × Rs. {base_fee:,.2f} = Rs. {fed_amount:,.2f}"
            )
        else:
            breakdown.append("2. FED / Sales Tax: Exempt / 0%")

        if intl_amount > 0:
            breakdown.append(
                f"3. Foreign Currency Conversion Surcharge ({intl_rate}% on Tx Amount Rs. {tx_amount:,.2f}): "
                f"({intl_rate}/100) × Rs. {tx_amount:,.2f} = Rs. {intl_amount:,.2f}"
            )

        if wht_amount > 0:
            filer_label = "Active Filer" if req.is_filer else "Non-Filer"
            breakdown.append(
                f"4. Advance Withholding Tax (Section 231A/236P - {filer_label} Rate {wht_rate}%): "
                f"({wht_rate}/100) × Rs. {(tx_amount if tx_amount > 0 else base_fee):,.2f} = Rs. {wht_amount:,.2f}"
            )

        breakdown.append(
            f"5. Total Customer Deduction: Rs. {base_fee:,.2f} + Rs. {fed_amount:,.2f}"
            + (f" + Rs. {intl_amount:,.2f}" if intl_amount > 0 else "")
            + (f" + Rs. {wht_amount:,.2f}" if wht_amount > 0 else "")
            + f" = Rs. {total_fee:,.2f}"
        )

        footnote_rule = None
        if fed_rate > 0:
            footnote_rule = f"Statutory Notice: FED/Sales Tax of {fed_rate}% is levied by tax authorities and is non-refundable by the bank."
        if not req.is_filer:
            footnote_rule = (footnote_rule or "") + " Non-filer surcharge applies in accordance with applicable tax statutory regulations."

        return TaxCalculateResponse(
            service_name=req.service_name or "Banking Service",
            base_fee=base_fee,
            fed_amount=fed_amount,
            wht_amount=wht_amount,
            intl_markup_amount=intl_amount,
            total_fee_charged=total_fee,
            breakdown_steps=breakdown,
            footnote_rule_applied=footnote_rule
        )
