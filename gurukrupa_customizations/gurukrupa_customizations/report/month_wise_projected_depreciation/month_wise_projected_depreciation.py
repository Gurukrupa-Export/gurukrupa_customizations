# Copyright (c) 2023, 8848 Digital LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, flt
from frappe import _
from erpnext.accounts.utils import get_fiscal_year


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_data(filters):
	conditions = get_conditions(filters)
	year_start_date, year_end_date = frappe.get_cached_value(
			"Fiscal Year", filters.get("fiscal_year"), ["year_start_date", "year_end_date"]
		)
	to_date = filters.get("to_date") or year_end_date
	Asset = frappe.qb.DocType("Asset")
	AssetFinanceBook = frappe.qb.DocType("Asset Finance Book")
	DepreciationSchedule = frappe.qb.DocType("Depreciation Schedule")

	subquery_acc_depreciation = (
        frappe.qb.from_(DepreciationSchedule)
        .select(frappe.query_builder.functions.Sum(DepreciationSchedule.depreciation_amount))
        .where(
            (DepreciationSchedule.parent == Asset.name) &
            (DepreciationSchedule.schedule_date <= to_date) &
            (DepreciationSchedule.docstatus == 1)  # Assuming docstatus should be 1 for accumulated depreciation
        )
    )

	subquery_previous_schedule_date = (
        frappe.qb.from_(DepreciationSchedule)
        .select(frappe.query_builder.functions.Max(DepreciationSchedule.schedule_date))
        .where(
            (DepreciationSchedule.schedule_date < to_date) &
            (DepreciationSchedule.docstatus == 1)  # Assuming docstatus should be 1 for previous schedule date
        )
    )
		
	subquery_current_schedule = (
        frappe.qb.from_(DepreciationSchedule)
        .select(
            DepreciationSchedule.parent,
            DepreciationSchedule.schedule_date.as_("current_schedule_date"),
            frappe.query_builder.functions.Sum(DepreciationSchedule.depreciation_amount).as_("depreciation_amount"),
            subquery_previous_schedule_date.as_("previous_schedule_date")
        )
        .where(
            (DepreciationSchedule.schedule_date >= to_date) &
            (DepreciationSchedule.docstatus == 1) &
            (DepreciationSchedule.schedule_date ==
             frappe.qb.from_(DepreciationSchedule)
             .select(frappe.query_builder.functions.Min(DepreciationSchedule.schedule_date))
             .where(
                 (DepreciationSchedule.schedule_date >= to_date) &
                 (DepreciationSchedule.docstatus == 1)
             ))
        )
        .groupby(DepreciationSchedule.parent, DepreciationSchedule.schedule_date)
    )
	#
	if filters.get("finance_book"):
		subquery_acc_depreciation = subquery_acc_depreciation.where(DepreciationSchedule.finance_book == filters.get("finance_book"))
		subquery_previous_schedule_date = subquery_previous_schedule_date.where(DepreciationSchedule.finance_book == filters.get("finance_book"))
		subquery_current_schedule = subquery_current_schedule.where(DepreciationSchedule.finance_book == filters.get("finance_book"))

	query = (
        frappe.qb.from_(Asset)
        .left_join(AssetFinanceBook).on(Asset.name == AssetFinanceBook.parent)
        .right_join(subquery_current_schedule).on(subquery_current_schedule.parent == Asset.name)
        .select(
            Asset.name.as_("asset"),
            Asset.asset_category,
            AssetFinanceBook.rate_of_depreciation,
            Asset.available_for_use_date,
            Asset.purchase_date,
            Asset.location,
            Asset.gross_purchase_amount.as_("purchase_value"),
            subquery_acc_depreciation.as_("acc_depreciation"),
            Asset.opening_accumulated_depreciation.as_("op_acc_depreciation"),
            subquery_current_schedule.current_schedule_date,
            subquery_current_schedule.depreciation_amount,
            subquery_current_schedule.previous_schedule_date
        )
        .where((Asset.docstatus == 1))
    )
	for condition in conditions:
		query = query.where(condition)

	schedules = query.run(as_dict=True)

	for row in schedules:
		if getdate(to_date) != row["current_schedule_date"]:
			start_date = max(year_start_date, row["purchase_date"])
			try:
				days = get_no_of_days(row["current_schedule_date"], (row["previous_schedule_date"] or start_date))
			except:
				frappe.msgprint(str(row))
			per_day = row['depreciation_amount'] / days
			row["total_days"] = days
			row["extra_days"] = get_no_of_days(getdate(to_date), (row["previous_schedule_date"] or start_date))
			row["depreciation"] = per_day*row["extra_days"]
		row["accumulated_depreciation"] = flt(row["op_acc_depreciation"]) + flt(row["acc_depreciation"])
		row["gross_block"] = row["purchase_value"] - flt(row["accumulated_depreciation"])
		row["net_block"] = row["gross_block"] - flt(row.get("depreciation"))
	return schedules


def get_columns(filters):
	columns = [
		{
			"label": _("Purchase Date"),
			"fieldname": "purchase_date",
			"fieldtype": "Date",
		},
		{
			"label": _("Asset Category"),
			"fieldname": "asset_category",
			"fieldtype": "Link",
			"options": "Asset Category",
		},
		{
			"label": _("Asset"),
			"fieldname": "asset",
			"fieldtype": "Link",
			"options": "Asset",
		},
		{
			"label": _("Rate of Depreciation"),
			"fieldname": "rate_of_depreciation",
			"fieldtype": "Percentage"
		},
		{
			"label": _("Location"),
			"fieldname": "location",
			"fieldtype": "Link",
			"options": "Location",
		},
		{
			"label": _("Purchase Value"),
			"fieldname": "purchase_value",
			"fieldtype": "Currency",
		},
		{
			"label": _("Accumulated Depreciation"),
			"fieldname": "accumulated_depreciation",
			"fieldtype": "Currency",
		},
		{
			"label": _("Gross Block"),
			"fieldname": "gross_block",
			"fieldtype": "Currency",
		},
		{
			"label": _("Depreciation"),
			"fieldname": "depreciation",
			"fieldtype": "Currency",
		},
		{"label": _("Net Block"), "fieldname": "net_block", "fieldtype": "Currency"},
	]
	return columns


def get_conditions(filters):
	from erpnext.accounts.utils import get_fiscal_year
	Asset = frappe.qb.DocType("Asset")
	conditions = []

	if filters.get("asset_category"):
		conditions.append(Asset.asset_category == filters.get("asset_category"))

	if filters.get("to_date"):
		conditions.append(Asset.purchase_date <= filters.get("to_date"))

	if filters.get("fiscal_year"):
		if filters.get("to_date"):
			fy_date = get_fiscal_year(filters.get("to_date"))
		else:
			year_end_date = frappe.get_cached_value("Fiscal Year", filters.get("fiscal_year"), "year_end_date")
			conditions.append(Asset.purchase_date <= year_end_date)

	if filters.get("location"):
		locations = frappe.parse_json(filters.get("location"))
		conditions.append(Asset.location.isin(locations))

	return conditions

def get_no_of_days(end_date, start_date):
	return abs((end_date-start_date).days)