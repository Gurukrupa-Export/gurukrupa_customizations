import frappe
from frappe.utils import getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
"""
Provided by sourav, navin
"""

def main(doc):
    def get_attendance_details():
        '''
            return {
                "01-01-2023" : {"working_hrs":"10.25", "late_entry": 0},
            }
        '''
        attendance_details = {}

        for attendance in frappe.db.get_all("Attendance", filters={
                "employee": doc.employee,
                "attendance_date": ("between", (doc.start_date, doc.end_date)),
                "status": ("Not In", ("Absent", "On Leave")),
                "shift": ("is", "set"),
                "docstatus": 1
            }, 
            fields=[
                "attendance_date", "net_working_hrs",
                "working_hours", "late_entry", "name", "early_exit"],  
            order_by="attendance_date asc"
        ):
            working_hrs = attendance.working_hours
            checkin = get_employee_checkin_details(attendance.name, "IN")
            if checkin:
                late_in_by = frappe.utils.time_diff_in_hours(checkin[0].time, checkin[0].shift_start)

            checkout = get_employee_checkin_details(attendance.name, "OUT")
            if checkout:
                late_exit_by = frappe.utils.time_diff_in_hours(checkout[0].time, checkout[0].shift_end)
                if late_exit_by > 0:
                    working_hrs = attendance.working_hours - late_exit_by

                early_exit_by = frappe.utils.time_diff_in_hours(checkout[0].shift_end, checkout[0].time)

            attendance_details[attendance['attendance_date']] = {
                "working_hrs": working_hrs,
                "late_entry": attendance.late_entry,
                "early_exit": attendance.early_exit,
                "early_exit_by": early_exit_by if early_exit_by > 0 else 0,
                "net_working_hrs": attendance.net_working_hrs,
                "late_in_by": late_in_by,
            }
        
        return attendance_details

    def get_employee_checkin_details(attendance, log_type):
        order_by="creation asc"
        if log_type == 'OUT':
            order_by="creation desc"
        
        return frappe.get_all(
            "Employee Checkin", 
            filters={"attendance": attendance, "log_type": log_type}, 
            fields=["shift_start", "time", "shift_end"], 
            order_by=order_by,
            limit=1
        )

    def get_shift():
        Attendance = frappe.qb.DocType("Attendance")
        
        shift = (
            frappe.qb.from_(Attendance)
            .select(Attendance.shift).distinct()
            .where(
                (Attendance.employee==doc.employee)
                & (Attendance.attendance_date.between(doc.start_date, doc.end_date))
                & (Attendance.shift.notnull())
            )
        ).run(pluck=True)

        if shift:
            return shift[0]

        return ''
    
    def get_working_hours_for_leaves():
        from_date = frappe.utils.getdate(doc.start_date)
        to_date = frappe.utils.getdate(doc.end_date)

        LeaveApplication = frappe.qb.DocType("Leave Application")
        leave_applications = (
            frappe.qb.from_(LeaveApplication)
            .select(
                LeaveApplication.employee,
                LeaveApplication.leave_type,
                LeaveApplication.from_date,
                LeaveApplication.to_date,
                LeaveApplication.total_leave_days,
            )
            .where(
                (LeaveApplication.employee == doc.employee)
                & (LeaveApplication.docstatus == 1)
                & (LeaveApplication.status == "Approved")
                & (
                    (LeaveApplication.from_date.between(from_date, to_date))
                    | (LeaveApplication.to_date.between(from_date, to_date))
                    | ((LeaveApplication.from_date < from_date) & (LeaveApplication.to_date > to_date))
                )
            )
        ).run(as_dict=True)
    
        leave_days = 0
    
        for leave_app in leave_applications:
            if leave_app.from_date >= frappe.utils.getdate(from_date) and leave_app.to_date <= frappe.utils.getdate(to_date):
                leave_days = leave_days + leave_app.total_leave_days
            else:
                if leave_app.from_date < getdate(from_date):
                    leave_app.from_date = from_date
                if leave_app.to_date > getdate(to_date):
                    leave_app.to_date = to_date
        
                leave_days = leave_days + frappe.utils.date_diff(leave_app.to_date, leave_app.from_date) + 1
            
        return leave_days * doc.shift_hours
    
    def get_holidays(dates, holiday_list, weekly_off=False):
        return frappe.db.get_all("Holiday", {
            "weekly_off": weekly_off,
            "parent": holiday_list,
            "holiday_date": ("between", [dates[0], dates[1]])
            }, ["holiday_date", "name"]
        )
    
    def get_working_hours_for_holidays(dates, holiday_list):
        holidays = get_holidays(dates=dates, holiday_list=holiday_list, weekly_off=False)
        return len(holidays) * doc.shift_hours
    
    def get_weekly_off_dates(dates, holiday_list):
        return get_holidays(dates=dates, holiday_list=holiday_list, weekly_off=True)
    
    def get_start_and_end_date():
        dates = frappe.db.get_value(
            "Employee", 
            doc.employee, 
            ["date_of_joining", "relieving_date"],
            as_dict=True
        )
        joining_date = dates.date_of_joining
        relieving_date = dates.relieving_date
        
        start_date = frappe.utils.getdate(doc.start_date)
        if joining_date and (frappe.utils.getdate(doc.start_date) <= joining_date <= frappe.utils.getdate(doc.end_date)):
            start_date = joining_date
            
        end_date = frappe.utils.getdate(doc.end_date)
        if relieving_date and (frappe.utils.getdate(doc.start_date) <= relieving_date <= frappe.utils.getdate(doc.end_date)):
            end_date = relieving_date
    
        return start_date, end_date
    
    
    def get_holiday_list_for_employee():
        holiday_list = frappe.db.get_value("Employee", doc.employee, "holiday_list")
        if not holiday_list:
            holiday_list = frappe.db.get_value("Company", doc.company, "default_holiday_list")
        
        return holiday_list
        

    def get_approved_ot_log():
        ot_log = {}
        for ot in frappe.db.get_all('OT Log', filters={
            "employee": doc.employee,
            "attendance_date": ("between", (doc.start_date, doc.end_date)),
            "is_cancelled": 0,
        }, fields=['attendance_date', 'allowed_ot']):
            ot_log[ot.attendance_date] = frappe.utils.flt(ot.allowed_ot.total_seconds()/3600)

        return ot_log

    def get_total_personal_outs():
        total_personal_outs = 0
        for personal_out in frappe.db.get_all('Personal Out Log', filters={
            "employee": doc.employee,
            "date": ("between", (doc.start_date, doc.end_date)),
            "approve": 1,
            "is_cancelled": 0,
        }, fields=[ 'out_time', 'in_time', 'total_hours']):
            total_personal_outs = total_personal_outs + personal_out.total_hours.seconds
        
        return total_personal_outs/3600
    
    def clear_default_amount():
        for earning in doc.earnings:
            earning.amount = 0
            earning.default_amount = 0
        
        for deduction in doc.deductions:
            earning.default_amount = 0


    shift = get_shift()
    dates = get_start_and_end_date()
    holiday_list = get_holiday_list_for_employee()
    
    doc.shift_hours = frappe.utils.flt(frappe.db.get_value("Shift Type", shift, "shift_hours")) or 10

    leave_hours = get_working_hours_for_leaves()
    holiday_hours = get_working_hours_for_holidays(dates=dates, holiday_list=holiday_list)
    attendance_details = get_attendance_details()
    approve_ot_logs = get_approved_ot_log()

    working_hrs = 0.0
    ot_hours = 0.0
    doc.extra_working_hours = 0.0
    total_late_marks = 0
    total_late_hrs = 0
    total_early_exit_hrs = 0

    for attendance_date in attendance_details:
        if attendance_details[attendance_date]['working_hrs'] >= doc.shift_hours:
            working_hrs = working_hrs + doc.shift_hours

        else:
            working_hrs = working_hrs + frappe.utils.flt(attendance_details[attendance_date]['net_working_hrs'])
        
        if attendance_date in approve_ot_logs:
            ot_hours = ot_hours + frappe.utils.flt(approve_ot_logs[attendance_date])
    
        total_late_marks = total_late_marks + attendance_details[attendance_date]['late_entry']

        if attendance_details[attendance_date]['late_entry']:
            total_late_hrs = total_late_hrs + attendance_details[attendance_date]['late_in_by']
        
        if attendance_details[attendance_date]['early_exit']:
            total_early_exit_hrs = total_early_exit_hrs + attendance_details[attendance_date]['early_exit_by']
    
    #check overtime on weekly off days
    for weekly_off in get_weekly_off_dates(dates=dates, holiday_list=holiday_list):
        if weekly_off.holiday_date in approve_ot_logs:
            ot_hours = ot_hours + frappe.utils.flt(approve_ot_logs[weekly_off.holiday_date])

    # explictly add working hours for leaves and holidays
    actual_working_hours = frappe.utils.flt(
        working_hrs
        + leave_hours
        + holiday_hours
    )

    #penalty for late marks
    if total_late_marks:
        late_mark_deductions_metrix = {0: 0, 1: 5, 2: 10, 3: 15}
        no_of_late_marks = total_late_marks // 5
        #setting default to 15 as if there are more than 15 late marks then also we have to deduct pay for one and a half day
        actual_working_hours = actual_working_hours - late_mark_deductions_metrix.get(no_of_late_marks, 15) 

    doc.actual_working_hours = frappe.utils.flt(actual_working_hours)
    doc.target_working_hours = frappe.utils.flt(doc.shift_hours * doc.total_working_days)

    base = frappe.db.get_value(
        "Salary Structure Assignment",
        {
            "employee": doc.employee,
            "salary_structure": doc.salary_structure,
            "from_date": ("<=", doc.start_date),
            "docstatus": 1,
        },
        "base"
    )
    
    if not doc.shift_hours:
        return

    if doc.target_working_hours:
        doc.hourly_rate = frappe.utils.flt(base / doc.target_working_hours)
    
    # refund personal out hours
    allowed_personal_hours = frappe.db.get_value("Employee", doc.employee, 'allowed_personal_hours')
    if allowed_personal_hours:
        allowed_personal_hours = frappe.utils.flt(allowed_personal_hours.seconds/3600)
    else:
        allowed_personal_hours = 0

    total_personal_outs = get_total_personal_outs()
    refund_hrs = min(allowed_personal_hours, (total_late_hrs+total_early_exit_hrs+total_personal_outs))
    
    doc.actual_working_hours = frappe.utils.flt(doc.actual_working_hours + refund_hrs)
    
    # if doc.actual_working_hours < doc.target_working_hours:
    #     hours_diff = doc.target_working_hours - doc.actual_working_hours
    #     if ot_hours:
    #         if ot_hours >= hours_diff:
    #             doc.actual_working_hours = doc.actual_working_hours + hours_diff
    #             doc.extra_working_hours = ot_hours - hours_diff
    #         else:
    #             doc.actual_working_hours = doc.actual_working_hours + ot_hours
    #             doc.extra_working_hours = 0
    # else:
    #     extra_working_hours = (doc.actual_working_hours -  doc.target_working_hours)
    #     doc.extra_working_hours = frappe.utils.flt(extra_working_hours)
    
    doc.extra_working_hours = frappe.utils.flt(ot_hours)
    
    if doc.actual_working_hours < doc.target_working_hours:
        doc.payment_days = doc.actual_working_hours/doc.shift_hours

    if doc.payment_days < doc.total_working_days:
        clear_default_amount()
        doc.calculate_net_pay()
        doc.compute_year_to_date()
        doc.compute_month_to_date()


def before_save(doc, method=None):
    try:
        if doc.consider_working_hours:
            main(doc)
    except Exception as e:
        frappe.log_error(
            title=f"Working hours calculation failed for salary slip {doc.name}", 
            message=e
        )
        raise


class CustomSalarySlip(SalarySlip):
    def get_holidays_for_employee(self, start_date, end_date):
        from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
        # HOLIDAYS_BETWEEN_DATES = "holidays_between_dates"
        holiday_list = get_holiday_list_for_employee(self.employee)
        # key = f"{holiday_list}:{start_date}:{end_date}"
        # holiday_dates = frappe.cache().hget(HOLIDAYS_BETWEEN_DATES, key)
        skip_weekly_offs = self.get("custom_only_weekly_offs",0)
        holiday_dates = get_holiday_dates_between(holiday_list, start_date, end_date, skip_weekly_offs)
        # frappe.cache().hset(HOLIDAYS_BETWEEN_DATES, key, holiday_dates)

        return holiday_dates


def get_holiday_dates_between(
	holiday_list: str,
	start_date: str,
	end_date: str,
	only_weekly_off: bool = False,
) -> list:
	Holiday = frappe.qb.DocType("Holiday")
	query = (
		frappe.qb.from_(Holiday)
		.select(Holiday.holiday_date)
		.where((Holiday.parent == holiday_list) & (Holiday.holiday_date.between(start_date, end_date)))
		.orderby(Holiday.holiday_date)
	)

	if only_weekly_off:
		query = query.where(Holiday.weekly_off == 1)

	return query.run(pluck=True)
