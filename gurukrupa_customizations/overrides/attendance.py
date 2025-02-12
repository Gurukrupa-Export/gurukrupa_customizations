import frappe

"""
Provided by sourav, navin
"""

def main(doc):
    def get_approved_personal_outs():
        total_personal_outs = 0
        for personal_out in frappe.db.get_all('Personal Out Log', filters={
            "employee": doc.employee,
            "date": doc.attendance_date,
            "approve": 1,
            "is_cancelled": 0,
        }, fields=[ 'out_time', 'in_time', 'total_hours']):
            total_personal_outs = total_personal_outs + personal_out.total_hours.seconds

        return total_personal_outs
    

    def get_shift_start_and_end_datetime():
        shift_details = frappe.db.get_value('Shift Type', doc.shift, ['start_time', 'end_time'], as_dict=1)
    
        start_time = shift_details.start_time
        end_time = shift_details.end_time
    
        attendance_date = doc.attendance_date
    
        shift_start_datetime = f'{attendance_date} {start_time}'
        shift_end_datetime = f'{attendance_date} {end_time}'
        
        shift_time = frappe.utils.time_diff_in_seconds(shift_end_datetime, shift_start_datetime)
        
        return shift_start_datetime, shift_end_datetime, shift_time
    
    time_diff = frappe.utils.time_diff_in_seconds(doc.out_time, doc.in_time)/3600

    personal_out = get_approved_personal_outs()
    shift_start_datetime, shift_end_datetime, shift_time = get_shift_start_and_end_datetime()
    shift_hours = shift_time / 3600
    
    net_working_seconds = shift_time

    late_exit = frappe.utils.time_diff_in_seconds(doc.out_time, shift_end_datetime)
    
    if not doc.late_entry and not doc.early_exit and not personal_out:
        doc.net_working_hrs = shift_hours
        
        if time_diff > shift_hours:
            doc.overtime_hrs = time_diff - shift_hours
    
    else:
        if doc.late_entry:
            late_in_by = frappe.utils.time_diff_in_seconds(shift_start_datetime, doc.in_time)
            net_working_seconds = net_working_seconds - late_in_by
        
        if doc.early_exit:
            early_exit_by = frappe.utils.time_diff_in_seconds(shift_end_datetime, doc.out_time)
            net_working_seconds = net_working_seconds - early_exit_by
        
        if personal_out:
            net_working_seconds = net_working_seconds - personal_out

        doc.net_working_hrs = net_working_seconds/3600  

        late_exit = frappe.utils.time_diff_in_seconds(doc.out_time, shift_end_datetime)
        if late_exit > 0:
            doc.overtime_hrs = late_exit/3600


def before_save(doc, method=None):
    try:
        main(doc)
    except Exception as e:
        frappe.log_error()