# Copyright (c) 2023, 8848 Digital LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from gke_customization.gke_hrms.doctype.monthly_in_out_log.monthly_in_out_log import (
	refresh_monthly_in_out_logs,
)

class PersonalOutLog(Document):

	def after_insert(self):
		self.update_monthly_in_out_log()

	def update_monthly_in_out_log(self):
		"""Refresh the Monthly In-Out Log of the day's attendance when Personal Out Log changes."""
		if not self.employee or not self.date:
			return

		attendance_name = frappe.db.get_value(
			"Attendance",
			{
				"employee": self.employee,
				"company": self.company,
				"attendance_date": getdate(self.date),
				"docstatus": ["<", 2],
			},
			"name",
		)
		if not attendance_name:
			return

		try:
			refresh_monthly_in_out_logs([attendance_name])
		except Exception:
			frappe.log_error(
				title="Monthly In-Out Log Update Error - Personal Out Log",
				message=frappe.get_traceback(),
			)

	def after_delete(self):
		self.update_monthly_in_out_log()