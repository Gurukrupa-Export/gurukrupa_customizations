// Copyright (c) 2023, 8848 Digital LLP and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Month-Wise Projected Depreciation"] = {
	"filters": [
		{
			"fieldname": "asset_category",
			"label": __("Asset Category"),
			"fieldtype": "Link",
			"options": "Asset Category",
		},
		{
			"fieldname": "fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": frappe.defaults.get_user_default("fiscal_year"),
			"reqd": 1,
			"on_change": function (query_report) {
				var fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) {
					return;
				}
				frappe.model.with_doc("Fiscal Year", fiscal_year, function (r) {
					var fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					var to_date = query_report.get_values().to_date;
					if (to_date < fy.year_start_date || to_date > fy.year_end_date) {
						query_report.set_filter_value({
							to_date: null
						});
						frappe.throw(__("Date must be in between Fiscal Year"));
					}
				});
				query_report.refresh()
			}
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"on_change": function (query_report) {
				var fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) {
					console.log('testds')
					return;
				}
				frappe.model.with_doc("Fiscal Year", fiscal_year, function (r) {
					var fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					var to_date = query_report.get_values().to_date;
					if (to_date < fy.year_start_date || to_date > fy.year_end_date) {
						query_report.set_filter_value({
							to_date: null
						});
						frappe.throw(__("Date must be in between Fiscal Year"));
					}
				});
				query_report.refresh()
			}
		},
		{
			"fieldname": "finance_book",
			"label": __("Finance Book"),
			"fieldtype": "Link",
			"options": "Finance Book",
		},
		{
			"fieldname":"location",
			"label": __("Location"),
			"fieldtype": "MultiSelectList",
			"options": "Location",
			get_data: function(txt) {
				return frappe.db.get_link_options("Location", txt);
			},
		},
	]
};
