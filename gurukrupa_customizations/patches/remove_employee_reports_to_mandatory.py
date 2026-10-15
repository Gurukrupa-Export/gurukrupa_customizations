import frappe


def execute():
	"""Drop the unconditional reqd Property Setter on Employee.reports_to.

	A first employee has no existing employee to report to, so an always
	mandatory reports_to can never be satisfied. The rule now lives in
	gke_hrms.doc_events.employee.validate_reports_to, which keeps Reports To
	mandatory for every employee except the first one of the company.
	"""
	frappe.db.delete(
		"Property Setter",
		{"doc_type": "Employee", "field_name": "reports_to", "property": "reqd"},
	)
