from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import User, Department, Leave, Announcement, Attendance, Payroll, Notification
from django.utils import timezone
from .decorators import admin_required, employee_required


def create_notification(recipient, message, actor=None):
    Notification.objects.create(recipient=recipient, actor=actor, message=message)


def notify_admins(message, actor=None):
    admin_users = User.objects.filter(role='admin', status='approved')
    for admin in admin_users:
        Notification.objects.create(recipient=admin, actor=actor, message=message)


def home(request):
    if request.user.is_authenticated:
        if request.user.role == 'admin':
            return redirect('admin_dashboard')
        else:
            return redirect('employee_dashboard')
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.status == 'pending':
                messages.error(request, 'Your account is pending approval.')
            elif user.status == 'rejected':
                messages.error(request, 'Your account has been rejected.')
            else:
                login(request, user)
                notify_admins(f"{user.get_full_name()} ({user.username}) signed in.", actor=user)
                if user.role == 'admin':
                    return redirect('admin_dashboard')
                else:
                    return redirect('employee_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'base/login.html')


def logout_view(request):
    # If an employee logs out while still clocked in for today, close their shift.
    if request.user.is_authenticated and request.user.role == 'employee':
        from .models import Attendance
        from django.utils import timezone
        today = timezone.localtime(timezone.now()).date()
        open_attendance = Attendance.objects.filter(employee=request.user, date=today, clock_out__isnull=True).first()
        if open_attendance:
            open_attendance.clock_out = timezone.localtime(timezone.now()).time()
            open_attendance.save()

    if request.user.is_authenticated:
        notify_admins(f"{request.user.get_full_name()} ({request.user.username}) logged out.", actor=request.user)

    logout(request)
    return redirect('login')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name  = request.POST.get('last_name')
        username   = request.POST.get('username')
        email      = request.POST.get('email')
        pass1      = request.POST.get('password1')
        pass2      = request.POST.get('password2')
        
        if pass1 != pass2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'base/register.html')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'base/register.html')
            
        user = User.objects.create_user(
            username=username,
            email=email,
            password=pass1,
            first_name=first_name,
            last_name=last_name,
            role='employee',
            status='pending'  # All self-registrations are pending by default
        )
        user.date_joined = timezone.localtime(timezone.now()).date()
        user.save()
        messages.success(request, 'Account created! Please wait for administrator approval before logging in.')
        return redirect('login')
        
    return render(request, 'base/register.html')


@admin_required
def admin_status_action(request, emp_id, action):
    employee = User.objects.get(id=emp_id, role='employee')
    if action == 'approve':
        employee.status = 'approved'
        messages.success(request, f"{employee.get_full_name()} has been APPROVED.")
    elif action == 'reject':
        employee.status = 'rejected'
        messages.error(request, f"{employee.get_full_name()} has been REJECTED.")
    employee.save()
    return redirect('admin_dashboard')



@admin_required
def admin_dashboard(request):
    from .models import Department, Leave
    today = timezone.now().date()

    total_employees  = User.objects.filter(role='employee', status='approved').count()
    pending_approvals = User.objects.filter(role='employee', status='pending').count()
    total_departments = Department.objects.count()
    on_leave_today   = Leave.objects.filter(
        status='approved',
        start_date__lte=today,
        end_date__gte=today
    ).count()
    recent_employees = User.objects.filter(role='employee').order_by('-date_joined')[:5]

    return render(request, 'admin/dashboard.html', {
        'total_employees':   total_employees,
        'pending_approvals': pending_approvals,
        'total_departments': total_departments,
        'on_leave_today':    on_leave_today,
        'recent_employees':  recent_employees,
    })


from .decorators import employee_required

@employee_required
def employee_dashboard(request):
    from .models import Announcement, Attendance
    from django.utils import timezone
    today = timezone.now().date()
    # Check if clocked in today
    attendance = Attendance.objects.filter(employee=request.user, date=today).first()
    announcements = Announcement.objects.all().order_by('-created_at')[:5]

    context = {
        'attendance': attendance,
        'announcements': announcements,
        'today_date': today,
    }
    return render(request, 'employee/dashboard.html', context)


@employee_required
def employee_clock_in_out(request):
    from .models import Attendance
    from django.utils import timezone
    local_now = timezone.localtime(timezone.now())
    today     = local_now.date()
    now_time  = local_now.time()
    
    attendance = Attendance.objects.filter(employee=request.user, date=today).first()
    
    if request.method == 'POST':
        if not attendance:
            # Clock IN
            Attendance.objects.create(
                employee=request.user,
                date=today,
                clock_in=now_time,
                status='present'
            )
            messages.success(request, f'Successfully clocked IN at {now_time.strftime("%I:%M %p")}. Have a great day!')
        elif attendance and not attendance.clock_out:
            # Clock OUT
            attendance.clock_out = now_time
            attendance.save()
            messages.success(request, f'Successfully clocked OUT at {now_time.strftime("%I:%M %p")}. Your shift has been recorded.')
        else:
            messages.error(request, 'You have already completed your shift for today.')
            
    return redirect('employee_dashboard')

@employee_required
def employee_profile(request):
    if request.method == 'POST':
        request.user.first_name     = request.POST.get('first_name', request.user.first_name)
        request.user.last_name      = request.POST.get('last_name',  request.user.last_name)
        request.user.email          = request.POST.get('email',      request.user.email)
        request.user.phone          = request.POST.get('phone',      request.user.phone)
        request.user.address        = request.POST.get('address',    request.user.address)
        request.user.bank_name      = request.POST.get('bank_name',  request.user.bank_name)
        request.user.pan_number     = request.POST.get('pan_number', request.user.pan_number)
        request.user.account_number = request.POST.get('account_number', request.user.account_number)
        dob = request.POST.get('date_of_birth')
        if dob:
            request.user.date_of_birth = dob
        request.user.save()
        messages.success(request, 'Your profile has been successfully updated.')
        return redirect('employee_profile')

    return render(request, 'employee/profile.html')

@employee_required
def employee_leaves(request):
    from datetime import datetime

    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str   = request.POST.get('end_date')
        reason         = request.POST.get('reason')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Please provide valid start and end dates in the format YYYY-MM-DD.')
            return redirect('employee_leaves')

        if end_date < start_date:
            messages.error(request, 'Leave end date cannot be earlier than start date.')
            return redirect('employee_leaves')

        requested_days = (end_date - start_date).days + 1
        remaining_days = request.user.get_monthly_leave_remaining()

        if leave_type != 'unpaid' and requested_days > remaining_days:
            messages.error(request, f'Insufficient leave balance: you requested {requested_days} days but only {remaining_days} days remain this month.')
            return redirect('employee_leaves')

        Leave.objects.create(
            employee=request.user,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason
        )
        messages.success(request, 'Your leave request has been sent to an administrator for approval.')
        return redirect('employee_leaves')

    leaves = Leave.objects.filter(employee=request.user).order_by('-applied_on')
    month_balance = request.user.monthly_leave_quota
    month_used = request.user.get_monthly_leave_used()
    month_remaining = request.user.get_monthly_leave_remaining()
    return render(request, 'employee/leaves.html', {
        'leaves': leaves,
        'monthly_leave_quota': month_balance,
        'monthly_leave_used': month_used,
        'monthly_leave_remaining': month_remaining,
    })


@employee_required
def employee_leave_cancel(request, leave_id):
    try:
        leave = Leave.objects.get(id=leave_id, employee=request.user)
    except Leave.DoesNotExist:
        messages.error(request, 'Leave request not found.')
        return redirect('employee_leaves')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('employee_leaves')

    if not leave.can_request_cancellation():
        messages.error(request, 'Cancellation window has expired or leave is not eligible for cancellation.')
        return redirect('employee_leaves')

    try:
        leave.request_cancellation()
        messages.success(request, 'Leave cancellation request submitted. Awaiting admin decision.')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as exc:
        messages.error(request, f'Unable to cancel leave: {exc}')

    return redirect('employee_leaves')


@admin_required
def admin_employee_list(request):
    employees = User.objects.filter(role='employee').order_by('-date_joined')
    return render(request, 'admin/employee_list.html', {'employees': employees})


@admin_required
def admin_employee_add(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        department_id = request.POST.get('department')
        designation = request.POST.get('designation')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('admin_employee_add')
            
        department = Department.objects.get(id=department_id) if department_id else None
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role='employee',
            status='approved',
            department=department,
            designation=designation
        )
        # Set additional fields
        doj_str = request.POST.get('date_joined')
        if doj_str:
            user.date_joined = doj_str
        else:
            user.date_joined = timezone.localtime(timezone.now()).date()
        user.bank_name = request.POST.get('bank_name', '')
        user.pan_number = request.POST.get('pan_number', '')
        user.account_number = request.POST.get('account_number', '')
        try:
            user.monthly_leave_quota = int(request.POST.get('monthly_leave_quota', 2))
        except (ValueError, TypeError):
            user.monthly_leave_quota = 2
        user.save()
        messages.success(request, f'Employee {user.get_full_name()} added successfully.')
        return redirect('admin_employees')
        
    departments = Department.objects.all()
    return render(request, 'admin/employee_form.html', {'departments': departments})


@admin_required
def admin_department_list(request):
    from django.db.models import Count
    # Annotate gets the number of employees associated with each department ID
    departments = Department.objects.annotate(employee_count=Count('user')).order_by('name')
    return render(request, 'admin/department_list.html', {'departments': departments})


@admin_required
def admin_department_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        if Department.objects.filter(name=name).exists():
            messages.error(request, 'A department with this name already exists.')
            return redirect('admin_department_add')
            
        Department.objects.create(name=name, description=description)
        messages.success(request, f'Department "{name}" added successfully.')
        return redirect('admin_departments')
        
    return render(request, 'admin/department_form.html')


@admin_required
def admin_leave_list(request):
    leaves = Leave.objects.all().order_by('-applied_on')
    return render(request, 'admin/leave_list.html', {'leaves': leaves})


@admin_required
def admin_leave_action(request, leave_id, action):
    from django.utils import timezone
    leave = Leave.objects.get(id=leave_id)

    if action == 'approve':
        leave.status = 'approved'
        leave.reviewed_by = request.user
        leave.reviewed_on = timezone.now()
        leave.save()
        messages.success(request, f"Leave request for {leave.employee.get_full_name()} has been successfully APPROVED.")

    elif action == 'reject':
        leave.status = 'rejected'
        leave.reviewed_by = request.user
        leave.reviewed_on = timezone.now()
        leave.save()
        messages.error(request, f"Leave request for {leave.employee.get_full_name()} has been REJECTED.")

    elif action == 'approve_cancel':
        try:
            leave.approve_cancellation(request.user)
            messages.success(request, f"Cancellation for {leave.employee.get_full_name()}'s leave has been APPROVED.")
        except ValidationError as e:
            messages.error(request, str(e))

    elif action == 'reject_cancel':
        try:
            leave.reject_cancellation(request.user)
            messages.error(request, f"Cancellation for {leave.employee.get_full_name()}'s leave has been REJECTED and restored.")
        except ValidationError as e:
            messages.error(request, str(e))

    else:
        messages.error(request, 'Unknown action.')

    return redirect('admin_leaves')


@admin_required
def admin_attendance(request):
    # Only show actual employee attendance entries, never admin user attendance records.
    from django.utils import timezone

    today = timezone.localtime(timezone.now()).date()
    attendances = Attendance.objects.filter(employee__role='employee').order_by('-date', '-clock_in')

    return render(request, 'admin/attendance_list.html', {
        'attendances': attendances,
        'today': today,
    })


@admin_required
def admin_announcements(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        Announcement.objects.create(title=title, content=content, created_by=request.user)

        # Broadcast notification to all active employees
        employees = User.objects.filter(role='employee', status='approved')
        message_text = f"New announcement: {title}. {content[:80]}"  # truncated for notification
        for employee in employees:
            create_notification(employee, message_text, actor=request.user)

        messages.success(request, 'Announcement posted successfully and notifications sent.')
        return redirect('admin_announcements')
        
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'admin/announcement_list.html', {'announcements': announcements})


@admin_required
def admin_payroll_list(request):
    payrolls = Payroll.objects.all().order_by('-year', '-month')
    return render(request, 'admin/payroll_list.html', {'payrolls': payrolls})


@admin_required
def admin_payroll_add(request):
    from django.utils import timezone
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        month_str = request.POST.get('month')
        basic_salary = float(request.POST.get('basic_salary') or 0)
        bonus = float(request.POST.get('bonus') or 0)
        deductions = float(request.POST.get('deductions') or 0)
        is_paid = request.POST.get('is_paid') == 'on'
        
        try:
            employee = User.objects.get(id=employee_id, role='employee')
            year, month = map(int, month_str.split('-'))
            
            Payroll.objects.create(
                employee=employee,
                month=month,
                year=year,
                basic_salary=basic_salary,
                allowances=bonus,
                deductions=deductions,
                status='paid' if is_paid else 'pending',
                generated_by=request.user,
                payment_date=timezone.now().date() if is_paid else None
            )
            messages.success(request, f'Payroll for {employee.get_full_name()} generated successfully.')
            return redirect('admin_payroll')
        except Exception as e:
            messages.error(request, f'Error generating payroll: {str(e)}')
            
    employees = User.objects.filter(role='employee')
    employee_data = []
    for emp in employees:
        employee_data.append({
            'id': emp.id,
            'employee_id': emp.employee_id or emp.username,
            'department': emp.department.name if getattr(emp, 'department', None) else 'N/A',
            'designation': emp.designation or 'N/A',
            'date_joined': emp.date_joined.strftime('%d-%b-%Y') if emp.date_joined else 'N/A',
            'bank_name': getattr(emp, 'bank_name', 'N/A') or 'N/A',
            'pan_number': getattr(emp, 'pan_number', 'N/A') or 'N/A',
            'account_number': getattr(emp, 'account_number', 'N/A') or 'N/A',
        })

    return render(request, 'admin/payroll_form.html', {'employees': employees, 'employee_data': employee_data})


def notification_mark_read(request, notification_id):
    notification = Notification.objects.filter(id=notification_id, recipient=request.user).first()
    if notification:
        notification.mark_as_read()
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def notification_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def number_to_words(n):
    if int(n) == 0: return "Zero Only"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
            "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def ntw(num):
        if num < 20: return ones[num]
        elif num < 100: return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")
        elif num < 1000: return ones[num // 100] + " Hundred" + (" and " + ntw(num % 100) if num % 100 != 0 else "")
        elif num < 100000: return ntw(num // 1000) + " Thousand" + (" " + ntw(num % 1000) if num % 1000 != 0 else "")
        elif num < 10000000: return ntw(num // 100000) + " Lakh" + (" " + ntw(num % 100000) if num % 100000 != 0 else "")
        else: return ntw(num // 10000000) + " Crore" + (" " + ntw(num % 10000000) if num % 10000000 != 0 else "")
        
    return ntw(int(n)).strip() + " Only"

def generate_pdf_response(payroll):
    from django.http import HttpResponse
    import io
    import datetime
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Heading1'], alignment=TA_CENTER, textColor=colors.HexColor("#1e3a8a"), fontSize=18)
    subtitle_style = ParagraphStyle(name='SubTitleStyle', parent=styles['Normal'], alignment=TA_CENTER, textColor=colors.gray, fontSize=10)
    
    # Header
    story.append(Paragraph("<b>ENTERPRISE HRMS</b>", title_style))
    story.append(Paragraph("123 Business Avenue, Tech District, City, Country<br/>Email: hr@enterprise.com | Phone: +1 234 567 8900", subtitle_style))
    story.append(Spacer(1, 20))
    
    month_name = datetime.date(payroll.year, payroll.month, 1).strftime('%B')
    story.append(Paragraph(f"<b>PAYSLIP FOR THE MONTH OF {month_name.upper()} {payroll.year}</b>", ParagraphStyle(name='P', alignment=TA_CENTER, fontSize=12, spaceAfter=20)))
    
    # Employee Details Table
    emp_id = payroll.employee.employee_id or payroll.employee.username or "N/A"
    doj_date = payroll.employee.date_joined or payroll.employee.date_joined
    doj = doj_date.strftime('%d-%b-%Y') if doj_date else "N/A"
    dept = payroll.employee.department.name if getattr(payroll.employee, 'department', None) else 'N/A'
    bank_name = getattr(payroll.employee, 'bank_name', None) or 'N/A'
    pan_no = getattr(payroll.employee, 'pan_number', None) or 'N/A'
    ac_number = getattr(payroll.employee, 'account_number', None) or 'N/A'

    emp_data = [
        ["Employee ID:", emp_id, "Department:", dept],
        ["Employee Name:", payroll.employee.get_full_name() or payroll.employee.username, "Designation:", payroll.employee.designation or "N/A"],
        ["Date of Joining:", doj, "Bank Name:", bank_name],
        ["PAN No:", pan_no, "A/C Number:", ac_number],
    ]
    
    t1 = Table(emp_data, colWidths=[100, 160, 100, 160])
    t1.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(t1)
    story.append(Spacer(1, 20))
    
    # Salary Details Table
    gross = float(payroll.basic_salary) + float(payroll.allowances)
    deductions = float(payroll.deductions)
    net = float(payroll.net_salary)
    
    sal_data = [
        ["EARNINGS", "AMOUNT (Rs.)", "DEDUCTIONS", "AMOUNT (Rs.)"],
        ["Basic Salary", f"{payroll.basic_salary:.2f}", "Tax & Deductions", f"{deductions:.2f}"],
        ["Allowances", f"{payroll.allowances:.2f}", "", ""],
        ["", "", "", ""],
        ["GROSS EARNINGS", f"{gross:.2f}", "TOTAL DEDUCTIONS", f"{deductions:.2f}"]
    ]
    
    t2 = Table(sal_data, colWidths=[160, 100, 160, 100])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e40af")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,1), (-1,-2), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e2e8f0")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(t2)
    story.append(Spacer(1, 20))
    
    # Net Pay
    story.append(Paragraph(f"<b>NET PAY: Rs. {net:.2f}</b>", ParagraphStyle(name='NP', alignment=TA_CENTER, fontSize=12, textColor=colors.HexColor("#16a34a"), spaceAfter=5)))
    story.append(Paragraph(f"<i>(Rupees {number_to_words(net)})</i>", ParagraphStyle(name='NW', alignment=TA_CENTER, fontSize=10, textColor=colors.gray)))
    story.append(Spacer(1, 50))
    
    # Signatures
    sig_data = [
        ["_"*30, "_"*30],
        ["Employer Signature", "Employee Signature"]
    ]
    t3 = Table(sig_data, colWidths=[260, 260])
    t3.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    story.append(t3)
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>This is a computer generated payslip and does not require a physical signature.</i>", ParagraphStyle(name='F', alignment=TA_CENTER, fontSize=8, textColor=colors.gray)))
    
    doc.build(story)
    
    buffer.seek(0)
    filename = f"payslip_{payroll.employee.username}_{month_name}_{payroll.year}.pdf"
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@admin_required
def admin_download_payslip(request, p_id):
    from .models import Payroll
    try:
        payroll = Payroll.objects.get(id=p_id)
        return generate_pdf_response(payroll)
    except:
        messages.error(request, "Payslip not found.")
        return redirect('admin_payroll')


@employee_required
def employee_payroll(request):
    from .models import Payroll
    payrolls = Payroll.objects.filter(employee=request.user).order_by('-year', '-month')
    return render(request, 'employee/payroll_list.html', {'payrolls': payrolls})


@employee_required
def employee_download_payslip(request, p_id):
    from .models import Payroll
    try:
        payroll = Payroll.objects.get(id=p_id, employee=request.user)
        return generate_pdf_response(payroll)
    except:
        messages.error(request, "Payslip not found.")
        return redirect('employee_payroll')


@employee_required
def employee_history(request):
    from .models import Attendance, Leave

    attendances = Attendance.objects.filter(employee=request.user).order_by('-date')
    leaves      = Leave.objects.filter(employee=request.user).order_by('-applied_on')

    total_present = attendances.filter(status='present').count()
    total_absent  = attendances.filter(status='absent').count()
    total_half    = attendances.filter(status='half_day').count()
    total_late    = attendances.filter(status='late').count()

    approved_leaves = leaves.filter(status='approved')
    total_leave_days = sum(
        l.duration_days for l in approved_leaves if l.duration_days is not None
    )

    leave_summary = {}
    for lt, label in Leave.LEAVE_TYPE_CHOICES:
        leave_summary[label] = leaves.filter(leave_type=lt, status='approved').count()

    context = {
        'attendances':      attendances,
        'leaves':           leaves,
        'total_present':    total_present,
        'total_absent':     total_absent,
        'total_half':       total_half,
        'total_late':       total_late,
        'total_leave_days': total_leave_days,
        'leave_summary':    leave_summary,
    }
    return render(request, 'employee/history.html', context)


@admin_required
def admin_employee_detail(request, emp_id):
    from .models import Attendance, Leave, Department
    from django.shortcuts import get_object_or_404

    employee = get_object_or_404(User, id=emp_id, role='employee')

    if request.method == 'POST':
        employee.first_name   = request.POST.get('first_name', employee.first_name)
        employee.last_name    = request.POST.get('last_name',  employee.last_name)
        employee.email        = request.POST.get('email',      employee.email)
        employee.designation  = request.POST.get('designation', employee.designation)
        employee.phone        = request.POST.get('phone',      employee.phone)
        employee.status       = request.POST.get('status',     employee.status)
        employee.bank_name   = request.POST.get('bank_name', employee.bank_name)
        employee.pan_number  = request.POST.get('pan_number', employee.pan_number)
        employee.account_number = request.POST.get('account_number', employee.account_number)
        doj = request.POST.get('date_joined')
        if doj:
            employee.date_joined = doj
        try:
            employee.monthly_leave_quota = int(request.POST.get('monthly_leave_quota', employee.monthly_leave_quota or 2))
        except (ValueError, TypeError):
            employee.monthly_leave_quota = employee.monthly_leave_quota or 2
        dept_id = request.POST.get('department')
        if dept_id:
            try:
                employee.department = Department.objects.get(id=dept_id)
            except Department.DoesNotExist:
                pass
        employee.save()
        messages.success(request, f"{employee.get_full_name()}'s profile has been updated successfully.")
        return redirect('admin_employee_detail', emp_id=emp_id)

    attendances  = Attendance.objects.filter(employee=employee).order_by('-date')
    leaves       = Leave.objects.filter(employee=employee).order_by('-applied_on')
    departments  = Department.objects.all()

    total_present = attendances.filter(status='present').count()
    total_absent  = attendances.filter(status='absent').count()
    approved_leaves = leaves.filter(status='approved')
    total_leave_days = sum(
        l.duration_days for l in approved_leaves if l.duration_days is not None
    )

    context = {
        'employee':         employee,
        'attendances':      attendances,
        'leaves':           leaves,
        'departments':      departments,
        'total_present':    total_present,
        'total_absent':     total_absent,
        'total_leave_days': total_leave_days,
    }
    return render(request, 'admin/employee_detail.html', context)


@admin_required
def admin_employee_edit_attendance(request, att_id):
    from .models import Attendance
    from django.shortcuts import get_object_or_404

    att = get_object_or_404(Attendance, id=att_id)

    if request.method == 'POST':
        att.status   = request.POST.get('status',    att.status)
        clock_in     = request.POST.get('clock_in')
        clock_out    = request.POST.get('clock_out')
        if clock_in:  att.clock_in  = clock_in
        if clock_out: att.clock_out = clock_out
        att.added_by = 'admin'
        att.save()
        messages.success(request, f'Attendance record for {att.date} updated successfully.')
        return redirect('admin_employee_detail', emp_id=att.employee.id)

    return render(request, 'admin/edit_attendance.html', {'att': att})


