import frappe
from frappe.utils import flt

from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
    SalaryStructureAssignment,
)

from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
    SALARY_COMPONENT_FLAGS,
)
from hrms.payroll.utils import sanitize_expression

# Salary Slip-only fields used in Salary Structure formulas.
# HRMS v16 evaluates formulas on Salary Structure Assignment first,
# so seed these fields to avoid NameError during SSA evaluation.
SLIP_ONLY_FORMULA_FIELDS = (
    "extra_working_hours",
    "hourly_rate",
    "custom_extra_payment_days",
    "custom_month",
    "_is_pf_applicable",
    "_is_physical_handicap",
)


def get_slip_formula_fields() -> dict:
     # Return Salary Slip values published during formula evaluation.
       return getattr(frappe.flags, "gurukrupa_slip_formula_fields", None) or {}


class CustomSalaryStructureAssignment(SalaryStructureAssignment):
    def _get_component_eval_context(self) -> frappe._dict:
        # Extend the evaluation context with Salary Slip-only fields.
        # Outside Salary Slip evaluation, use safe default values.
        data = super()._get_component_eval_context()
        slip_fields = get_slip_formula_fields()

        for fieldname in SLIP_ONLY_FORMULA_FIELDS:
            if fieldname == "custom_month":
                if slip_fields.get("custom_month") is not None:
                    data.custom_month = slip_fields["custom_month"]
                else:
                    # no slip in scope (SSA save/CTC): fall back to the seeded
                    # full-cycle period month
                    data.custom_month = frappe.utils.getdate(data.start_date).month
            elif fieldname not in data:
                data[fieldname] = slip_fields.get(fieldname, 0)

        return data


def build_evaluated_component_row(struct_row) -> frappe._dict:
    # Recreate an evaluated component row for components skipped
    # during SSA evaluation because their condition depended on
    # Salary Slip-only fields.
    row = frappe._dict(
        default_amount=0,
        amount=flt(struct_row.amount),
        condition=sanitize_expression(struct_row.condition),
        formula=sanitize_expression(struct_row.formula),
        precision=struct_row.precision("amount"),
    )
    for field in SALARY_COMPONENT_FLAGS:
        row[field] = struct_row.get(field)
    return row
