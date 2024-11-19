import frappe

"""
Provided by sourav, navin
"""

def before_save(doc, method=None):
    doc.shift_hours = frappe.utils.time_diff_in_hours(doc.end_time, doc.start_time)

    # shift spanning over 2 days
    # eg: 09:00 to 01:00 = -8
    # -8 + 12 = 4 hour shift

    if doc.shift_hours < 0:
        doc.shift_hours = doc.shift_hours + 12

def set_date_value():
    for row in frappe.db.get_all("Shift Type", {"enable_auto_attendance": 1}):
        doc = frappe.get_doc("Shift Type", row)
        doc.last_sync_of_checkin = frappe.utils.now()
        doc.flags.ignore_permissions = True
        doc.save()