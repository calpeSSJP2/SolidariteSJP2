from django.utils import timezone
from .models import MeetingAttendance, SJP2_Account


def calculate_penalty(attendance: MeetingAttendance):
    """
    Applies penalty rules based on attendance status.
    """
    if attendance.status == MeetingAttendance.AttendanceStatus.LATE:
        return 500
    elif attendance.status == MeetingAttendance.AttendanceStatus.ABSENT:
        return 1000
    return 0


def update_attendance_status(attendance: MeetingAttendance, check_in_time=None):
    """
    Determines if the user is late or on time.
    """
    if not check_in_time:
        check_in_time = timezone.now()

    attendance.check_in_time = check_in_time
    meeting_datetime = timezone.make_aware(
        timezone.datetime.combine(attendance.meeting.date, attendance.meeting.start_time)
    )

    late_limit = meeting_datetime + timezone.timedelta(minutes=15)
    if check_in_time <= late_limit:
        attendance.status = MeetingAttendance.AttendanceStatus.PRESENT
    else:
        attendance.status = MeetingAttendance.AttendanceStatus.LATE

    attendance.penalty_amount = calculate_penalty(attendance)
    attendance.save()


def apply_penalty_transfer(attendance: MeetingAttendance):
    """
    Transfers the penalty amount from the member's account to the SJP2 penalty account.
    """
    from .models import MemberAccount  # Avoid circular import

    penalty_account = SJP2_Account.get_account_by_purpose('penalty')
    member_account = attendance.member.account

    if not member_account or not penalty_account:
        return False

    amount = attendance.penalty_amount
    if amount > 0 and member_account.balance >= amount:
        member_account.balance -= amount
        penalty_account.balance += amount
        member_account.save()
        penalty_account.save()
        return True
    return False
