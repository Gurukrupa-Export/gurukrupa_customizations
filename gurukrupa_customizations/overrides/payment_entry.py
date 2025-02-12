import frappe
from frappe import _
import erpnext
from frappe.utils import flt
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry

def validate(doc, method=None):
    if doc.get("is_inter_unit"):
        set_deductions(doc)

def set_deductions(doc):
    for d in doc.get("references"):
        if not d.cost_center:
            d.cost_center = frappe.db.get_value(d.reference_doctype, d.reference_name, "cost_center")
    ccs = [d.get("cost_center") for d in (doc.get("references") or [])] + [doc.cost_center]
    ccs = frappe.db.get_values("Cost Center", {"name":["in",ccs]},["name","inter_unit_account"], as_dict=1)
    cc_map = {d.get("name"):d.get("inter_unit_account") for d in ccs}
    for d in doc.get("references"):
        if doc.cost_center != d.cost_center:
            if not (cc_map[doc.cost_center] and cc_map[d.cost_center]):
                frappe.throw(_("Please set Inter Unit Account in Cost Center"))
            filters1 = {
                "cost_center": d.cost_center,
                "account": cc_map[doc.cost_center],
                "amount": -d.allocated_amount
            }
            filters2 = {
                "cost_center": doc.cost_center,
                "account": cc_map[d.cost_center],
                "amount": d.allocated_amount
            }
            if not doc.get("deductions", filters=filters1):
                doc.append("deductions",filters1)
            if not doc.get("deductions", filters=filters2):
                doc.append("deductions",filters2)

class CustomPaymentEntry(PaymentEntry):
    def add_party_gl_entries(self, gl_entries):
        if self.party_account:
            if self.payment_type == "Receive":
                against_account = self.paid_to
            else:
                against_account = self.paid_from

            party_gl_dict = self.get_gl_dict(
                {
                    "account": self.party_account,
                    "party_type": self.party_type,
                    "party": self.party,
                    "against": against_account,
                    "account_currency": self.party_account_currency,
                    "cost_center": self.cost_center,
                },
                item=self,
            )

            dr_or_cr = (
                "credit" if erpnext.get_party_account_type(self.party_type) == "Receivable" else "debit"
            )

            for d in self.get("references"):
                cost_center = d.cost_center if self.get("is_inter_unit") else self.cost_center
                if d.reference_doctype == "Sales Invoice" and not cost_center:
                    cost_center = frappe.db.get_value(d.reference_doctype, d.reference_name, "cost_center")
                gle = party_gl_dict.copy()
                gle.update(
                    {
                        "against_voucher_type": d.reference_doctype,
                        "against_voucher": d.reference_name,
                        "cost_center": cost_center,
                    }
                )

                allocated_amount_in_company_currency = flt(
                    flt(d.allocated_amount) * flt(d.exchange_rate), self.precision("paid_amount")
                )

                gle.update(
                    {
                        dr_or_cr + "_in_account_currency": d.allocated_amount,
                        dr_or_cr: allocated_amount_in_company_currency,
                    }
                )

                gl_entries.append(gle)

            if self.unallocated_amount:
                exchange_rate = self.get_exchange_rate()
                base_unallocated_amount = self.unallocated_amount * exchange_rate

                gle = party_gl_dict.copy()

                gle.update(
                    {
                        dr_or_cr + "_in_account_currency": self.unallocated_amount,
                        dr_or_cr: base_unallocated_amount,
                    }
                )

                gl_entries.append(gle)