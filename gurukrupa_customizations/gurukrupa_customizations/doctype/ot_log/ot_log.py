# Copyright (c) 2023, 8848 Digital LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from gke_customization.gke_hrms.doctype.monthly_in_out_log.monthly_in_out_log import get_attendance_details_by_date, fmt_td_or_value


class OTLog(Document):
	
	def after_insert(self):
		self.update_monthly_in_out_log()

	def update_monthly_in_out_log(self):
		"""
		Recalculate Monthly In-Out Log when OT Log changes
		"""
		try:
			if not self.employee or not self.date:
				return

			attendance_date = getdate(self.date)

			mil_name = frappe.db.get_value(
				"Monthly In-Out Log",
				{
					"employee": self.employee,
					"company": self.company,
					"attendance_date": attendance_date,
					"docstatus": ["in", [0, 1]],
				},
				"name",
			)

			if not mil_name:
				return

			mil = frappe.get_doc("Monthly In-Out Log", mil_name)

			res = get_attendance_details_by_date(
				mil.company,
				mil.employee,
				attendance_date
			)

			records = res.get("records") or []
			if not records:
				return

			record = records[0]

			mil.db_set("spent_hrs", fmt_td_or_value(record.get("spent_hrs")))
			mil.db_set("net_wrk_hrs" , fmt_td_or_value(record.get("net_wrk_hrs")))
			mil.db_set("p_out_hrs", fmt_td_or_value(record.get("p_out_hrs")))
			mil.db_set("ot_hrs", fmt_td_or_value(record.get("ot_hours"))) 
		except Exception as e:
			frappe.log_error(message=f"Error updating Monthly In-Out Log: {e}", title="Monthly In-Out Log Update Error - OT Log")

	def after_delete(self):
		self.update_monthly_in_out_log()
		
		