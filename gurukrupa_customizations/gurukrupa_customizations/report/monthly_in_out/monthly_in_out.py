# Copyright (c) 2023, 8848 Digital LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import timedelta, datetime
from frappe.utils import flt, getdate, add_days, format_time, today, add_to_date, get_time
from gurukrupa_customizations.gurukrupa_customizations.doctype.manual_punch.manual_punch import get_checkins
from frappe.query_builder.functions import Count, Date, Concat, IfNull, Sum
from frappe.query_builder import CustomFunction

STATUS = {
	"Absent" : "A",
	"Present" : "P",
	"Half Day" : "HD",
	"Paid Leave" : "PL",
	"Casual Leave" : "CL",
	"Sick Leave" : "SL",
	"Leave Without Pay" : "LWP",
	"Outdoor Duty" : "OD",
	"Maternity Leave" : "ML",
}

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

# sec_to_time(at.working_hours*3600)
def get_data(filters=None):
	
	Attendance = frappe.qb.DocType("Attendance")
	Employee = frappe.qb.DocType("Employee")
	ShiftType = frappe.qb.DocType("Shift Type")
	PersonalOutLog = frappe.qb.DocType("Personal Out Log")
	OTLog = frappe.qb.DocType("OT Log")

	conditions = get_conditions(filters)

	# To_Seconds = CustomFunction("TIME_TO_SEC", ["date"])
	# ifelse = CustomFunction("IF", ["condition", "then", "else"])
	# Time_Diff = CustomFunction("TIMEDIFF", ["cur_date", "due_date"])
	# Time = CustomFunction("Time", ["time"])
	# Sec_To_Time = CustomFunction("SEC_TO_TIME", ["date"])

	TIME_FORMAT = CustomFunction('TIME_FORMAT', ['time', 'format'])
	TIMEDIFF = CustomFunction('TIMEDIFF', ['time1', 'time2'])
	SEC_TO_TIME = CustomFunction('SEC_TO_TIME', ['seconds'])
	TIME_TO_SEC = CustomFunction('TIME_TO_SEC', ['time'])
	IF = CustomFunction('IF', ['condition', 'true_expr', 'false_expr'])
	TIMESTAMP = CustomFunction('TIMESTAMP', ['date', 'time'])
	TIME = CustomFunction('TIME', ['time'])

	# Personal Out Log subquery
	pol_subquery = (
		frappe.qb.from_(PersonalOutLog)
		.select(
			PersonalOutLog.employee, 
			PersonalOutLog.date, 
			SEC_TO_TIME(IfNull(Sum(TIME_TO_SEC(PersonalOutLog.total_hours)), 0)).as_('hrs')
			)
		.where(PersonalOutLog.is_cancelled == 0)
		.groupby(PersonalOutLog.employee, PersonalOutLog.date)
	).as_('pol')

	# OT Log subquery
	ot_subquery = (
		frappe.qb.from_(OTLog)
		.select('*')
		.where(OTLog.is_cancelled == 0)
	).as_('ot')

    
	query = (
		frappe.qb.from_(Attendance)
		.left_join(Employee).on(Attendance.employee == Employee.name)
		.left_join(ShiftType).on(Employee.default_shift == ShiftType.name)
		.left_join(pol_subquery).on(
			(Attendance.attendance_date == pol_subquery.date) &
			(Attendance.employee == pol_subquery.employee)
		)
		.left_join(ot_subquery).on(
			(Attendance.attendance_date == ot_subquery.attendance_date) &
			(Attendance.employee == ot_subquery.employee)
		)
		.select(
			Attendance.attendance_date,
			Concat(TIME_FORMAT(ShiftType.start_time, "%H:%i:%s"), " TO ", TIME_FORMAT(ShiftType.end_time, "%H:%i:%s")).as_('shift'),
			TIME(Attendance.in_time).as_('in_time'),
			TIME(Attendance.out_time).as_('out_time'),
			TIMEDIFF(Attendance.out_time, Attendance.in_time).as_('spent_hours'),
			Attendance.late_entry,
			IF(Attendance.late_entry, TIMEDIFF(TIME(Attendance.in_time), ShiftType.start_time), None).as_('late_hrs'),
			IF(Attendance.early_exit, TIMEDIFF(ShiftType.end_time, TIME(Attendance.out_time)), None).as_('early_hrs'),
			pol_subquery.hrs.as_('p_out_hrs'),
			SEC_TO_TIME(
				IF(
					(Attendance.attendance_request.isnotnull() |
					((Attendance.status == "On Leave") & 
					(Attendance.leave_type.isin(frappe.db.get_list('Leave Type', filters={'is_lwp': 0}, pluck='name'))))),
					ShiftType.shift_hours * 3600,
					IF(Attendance.out_time, TIME_TO_SEC(TIMEDIFF(Attendance.out_time, Attendance.in_time)), Attendance.working_hours * 3600)
				)
				+ IF((Attendance.late_entry == 0) & (TIME(Attendance.in_time) > ShiftType.start_time),
					TIME_TO_SEC(TIMEDIFF(TIME(Attendance.in_time), ShiftType.start_time)), 0)
				- IF(TIME(Attendance.in_time) < ShiftType.start_time,
					TIME_TO_SEC(TIMEDIFF(ShiftType.start_time, TIME(Attendance.in_time))), 0)
				- IF(Attendance.out_time > TIMESTAMP(Date(Attendance.in_time), ShiftType.end_time),
					TIME_TO_SEC(TIMEDIFF(Attendance.out_time, TIMESTAMP(Date(Attendance.in_time), ShiftType.end_time))), 0)
				- IfNull(TIME_TO_SEC(pol_subquery.hrs), 0)
				+ (
					frappe.qb.from_(PersonalOutLog)
					.select(IfNull(Sum(TIME_TO_SEC(PersonalOutLog.total_hours)), 0))
					.where(
						(PersonalOutLog.is_cancelled == 0) &
						(PersonalOutLog.employee == Attendance.employee) &
						(PersonalOutLog.date == Attendance.attendance_date) &
						(PersonalOutLog.out_time >= ShiftType.end_time)
					)
				)
			).as_('net_wrk_hrs'),
			ShiftType.shift_hours,
			IF((ShiftType.working_hours_threshold_for_half_day > Attendance.working_hours) & (Attendance.working_hours > 0), 1, 0).as_('lh'),
			ot_subquery.allowed_ot.as_('ot_hours'),
			IfNull(Attendance.leave_type, Attendance.status).as_('status'),
			Attendance.attendance_request
		)
		.where(
			(Attendance.docstatus == 1)
		)
		.orderby(Attendance.attendance_date, order=frappe.qb.asc)
	)

	for condition in conditions:
		query = query.where(condition)

	data = query.run(as_dict=1)
	
	if not data:
		return
	
	data = process_data(data, filters)
	totals = get_totals(data, filters.get("employee"))
	data += totals
	return data

def get_totals(data, employee):	
	totals = {
		"status": "Total Hours",
		"net_wrk_hrs": timedelta(0),
		"spent_hours": timedelta(0),
		"late_hrs": timedelta(0),
		"early_hrs": timedelta(0),
		"p_out_hrs": timedelta(0),
		"ot_hours": timedelta(0),
		"total_pay_hrs": timedelta(0),
	}
	late_count = 0
	penalty_days = 0
	for row in data:
		totals["net_wrk_hrs"] += (row.get("net_wrk_hrs") or timedelta(0))
		totals["total_pay_hrs"] += (row.get("total_pay_hrs") or timedelta(0))
		totals["ot_hours"] += (row.get("ot_hours") or timedelta(0))
		totals["early_hrs"] += (row.get("early_hrs") or timedelta(0))
		totals["late_hrs"] += (row.get("late_hrs") or timedelta(0))
		totals["p_out_hrs"] += (row.get("p_out_hrs") or timedelta(0))
		totals["spent_hours"] += (row.get("spent_hours") or timedelta(0))
		if row.get("late_entry"):
			late_count += 1
		if row.get("shift_hours"):
			totals["shift_hours"] = row.get("shift_hours")
	
	if late_count > 4 and late_count < 10:
		penalty_days = 0.5
	if late_count >= 10 and late_count < 15:
		penalty_days = 1
	if late_count > 15:
		penalty_days = 1.5

	total_days = {"status":"Total Days"}
	conversion_factor = 3600 * flt(totals["shift_hours"])

	penalty_hrs = timedelta(hours=flt(totals["shift_hours"])*penalty_days)
	for key,value in totals.items():
		if key in ["status","shift_hours"]:
			continue
		total_days[key] = flt(value.total_seconds() / conversion_factor, 2)

	refund = {
		"ot_hours": "Refund Min(P.Hrs)",
		"total_pay_hrs" : min(frappe.db.get_value("Employee",employee,'allowed_personal_hours') or timedelta(0), (totals["early_hrs"]+totals["late_hrs"]+totals["p_out_hrs"]))
	}

	penalty_for_late_entry = {
		"ot_hours": "Penalty in Days",
		"total_pay_hrs" : penalty_days
	}

	net_pay_hrs = {
		"ot_hours": "Net Hrs",
		"total_pay_hrs" : totals["total_pay_hrs"] + refund["total_pay_hrs"] - penalty_hrs
	}

	net_pay_days = {
		"ot_hours": "Net Days",
		"total_pay_hrs" : flt(net_pay_hrs['total_pay_hrs'].total_seconds() / conversion_factor, 2)
	}

	net_pay_hrs_wo_ot = {
		"ot_hours": "Net Hrs w/o OT",
		"total_pay_hrs" : totals["total_pay_hrs"] + refund["total_pay_hrs"] - penalty_hrs - totals["ot_hours"]
	}

	net_pay_days_wo_ot = {
		"ot_hours": "Net Days w/o OT",
		"total_pay_hrs" : flt(net_pay_hrs_wo_ot['total_pay_hrs'].total_seconds() / conversion_factor, 2)
	}

	return [totals, total_days, refund, penalty_for_late_entry, net_pay_hrs, net_pay_days, net_pay_hrs_wo_ot, net_pay_days_wo_ot]

def process_data(data, filters):
	employee = filters.get("employee")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	processed = {}
	result = []
	holidays = []
	wo = []
	emp_det = frappe.db.get_value("Employee", employee, ["default_shift","holiday_list","date_of_joining"], as_dict=1)
	shift = emp_det.get("default_shift")
	shift_det = frappe.db.get_value("Shift Type", shift, ['shift_hours','holiday_list','start_time', 'end_time'], as_dict=1)
	shift_hours = flt(shift_det.get("shift_hours"))
	shift_name = f"{format_time(shift_det.get('start_time'))} To {format_time(shift_det.get('end_time'))}"
	
	EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
	addition_day = add_days(to_date,1)
	checkins = (
		frappe.qb.from_(EmployeeCheckin)
		.select(
			Date(EmployeeCheckin.time).as_("login_date"),
			EmployeeCheckin.attendance,
			Count(EmployeeCheckin.name).as_("cnt")
		)
		.where(
			(EmployeeCheckin.time.between(from_date, addition_day)) &
			(EmployeeCheckin.employee == employee)
		)
		.groupby(EmployeeCheckin.attendance)
	).run(as_dict=True)
	
	checkins = {row.login_date: row.cnt for row in checkins}
	od = frappe.get_list("Employee Checkin",{'employee':employee,'source':"Outdoor Duty", "time": ['between',[from_date,add_days(to_date,1)]]},'date(time) as login_date', pluck='login_date',group_by='login_date')
	if shift and not emp_det.get('holiday_list'):
			emp_det['holiday_list'] = shift_det.get("holiday_list")
	
	if hl_name:=emp_det.get('holiday_list'):
		holidays = frappe.get_list("Holiday", {"parent": hl_name,
					"holiday_date":["between",[from_date, to_date]]}, ["holiday_date","weekly_off"], ignore_permissions=1)
		wo = [row.holiday_date for row in holidays if row.weekly_off]
		holidays = [row.holiday_date for row in holidays if not row.weekly_off]

	for row in data:
		if row.lh:
			row.status = 'LH'
		shift_hours_in_sec = row.shift_hours*3600
		if row.net_wrk_hrs.total_seconds() > shift_hours_in_sec or (shift_hours_in_sec - row.net_wrk_hrs.total_seconds()) < 60:
			row.net_wrk_hrs = timedelta(hours=row.shift_hours)
		row["total_pay_hrs"] = row.net_wrk_hrs + (row.get("ot_hours") or timedelta(0))
		row.status = STATUS.get(row.status) or row.status
		processed[row.attendance_date] = row

	ot_for_wo = frappe.get_all("OT Log", {"employee":employee,"attendance_date": ["between",[from_date,to_date]], "is_cancelled":0}, ["attendance_date","allowed_ot as ot_hours", "first_in as in_time", "last_out as out_time"])
	ot_for_wo = {row.attendance_date: row for row in ot_for_wo}
	date_range = get_date_range(from_date, to_date)
	for date in date_range:
		row = processed.get(date,ot_for_wo.get(date,{}))
		if date in od:
			row["status"] = "OD"
			if ot_hours:=row.get("ot_hours"):
				row['total_pay_hrs'] = ot_hours
		elif date in wo and (date >= getdate(emp_det.get("date_of_joining"))):
			status = "WO"
			date_time = datetime.combine(getdate(date), get_time(shift_det.start_time))
			if first_in_last_out := get_checkins(employee,date_time):		
				row["in_time"] = get_time(first_in_last_out[0].get("time"))
				row["out_time"] = get_time(first_in_last_out[-1].get("time"))
			if ot_hours:=row.get("ot_hours"):
				row['total_pay_hrs'] = ot_hours
		elif (date in holidays) and (date >= getdate(emp_det.get("date_of_joining"))):
			status = "H"
			row['net_wrk_hrs'] = timedelta(hours=shift_hours)
			row['total_pay_hrs'] = timedelta(hours=shift_hours)
		else:
			status = "XX"
		if count:=checkins.get(date):
			if count %2 != 0:
				row["status"] = "ERR"
		temp = {
			"login_date": date,
			"shift": shift_name,
			"status": status
		}
		if not row.get("spent_hours"):
			row["spent_hours"] = None
		temp.update(row)
		result.append(temp)
	return result
	
def get_columns(filters=None):
	columns = [
		{
			"label": _("Login Date"),
			"fieldname": "login_date",
			"fieldtype": "Date"
		},
		{
			"label": _("Shift Name"),
			"fieldname": "shift",
			"fieldtype": "Data"
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Late"),
			"fieldname": "late_entry",
			"fieldtype": "Data"
		},
		{
			"label": _("In Time"),
			"fieldname": "in_time",
			"fieldtype": "Data",
			"width":80
		},
		{
			"label": _("Out Time"),
			"fieldname": "out_time",
			"fieldtype": "Data"
		},
		{
			"label": _("Spent Hrs"),
			"fieldname": "spent_hours",
			"fieldtype": "Data"
		},
		{
			"label": _("Late Hrs"),
			"fieldname": "late_hrs",
			"fieldtype": "Data"
		},
		{
			"label": _("Early Hrs"),
			"fieldname": "early_hrs",
			"fieldtype": "Data"
		},
		{
			"label": _("P.Out Hrs"),
			"fieldname": "p_out_hrs",
			"fieldtype": "Data"
		},
		{
			"label": _("Net Wrk Hrs"),
			"fieldname": "net_wrk_hrs",
			"fieldtype": "Data"
		},
		{
			"label": _("OT Hrs"),
			"fieldname": "ot_hours",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Total Pay Hrs"),
			"fieldname": "total_pay_hrs",
			"fieldtype": "Data"
		}
	]

	return columns

def get_conditions(filters):

	Attendance = frappe.qb.DocType("Attendance")

	if not (filters.get("from_date") and filters.get("to_date")):
		frappe.throw(_("From & To Dates are mandatory")) 
	
	conditions = [
        (Attendance.attendance_date.between(filters.get("from_date"), filters.get("to_date")))
    ]
	if filters.get("employee"):
		conditions.append(Attendance.employee == filters.get("employee"))
    
	return conditions

def get_date_range(start_date, end_date):
	import datetime
	start_date = getdate(start_date)
	end_date = getdate(end_date)

	range = []
	delta = datetime.timedelta(days=1)
	current_date = start_date

	while current_date <= end_date:
		range.append(current_date)
		current_date += delta

	return range

@frappe.whitelist()
def get_month_range():
	from frappe.utils.dateutils import get_dates_from_timegrain, get_period
	end = today()
	start = add_to_date(end, months=-12)
	periodic_range = get_dates_from_timegrain(start, end, "Monthly")
	periods = [get_period(row) for row in periodic_range]
	periods.reverse()
	return periods
