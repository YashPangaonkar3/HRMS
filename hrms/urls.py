from django.urls import path
from . import views

urlpatterns = [
    # Core Auth & Dashboards
    path('',                    views.home,                name='home'),
    path('login/',              views.login_view,           name='login'),
    path('logout/',             views.logout_view,          name='logout'),
    path('admin-dashboard/',    views.admin_dashboard,      name='admin_dashboard'),
    path('employee-dashboard/', views.employee_dashboard,   name='employee_dashboard'),
    path('register/',           views.register,             name='register'),

    # Phase 5: Employee Features
    path('employee-dashboard/profile/',       views.employee_profile,     name='employee_profile'),
    path('employee-dashboard/leaves/',        views.employee_leaves,      name='employee_leaves'),
    path('employee-dashboard/leaves/<int:leave_id>/cancel/', views.employee_leave_cancel, name='employee_leave_cancel'),
    path('employee-dashboard/clock-in-out/',  views.employee_clock_in_out,name='employee_clock_in_out'),
    path('employee-dashboard/payroll/',       views.employee_payroll,     name='employee_payroll'),
    path('employee-dashboard/payroll/download/<int:p_id>/', views.employee_download_payslip, name='employee_download_payslip'),

    # Phase 4.1: Employee Management (Admin)
    path('admin-dashboard/employees/',        views.admin_employee_list,  name='admin_employees'),
    path('admin-dashboard/employees/add/',    views.admin_employee_add,   name='admin_employee_add'),

    # Phase 4.2: Department Management
    path('admin-dashboard/departments/',          views.admin_department_list, name='admin_departments'),
    path('admin-dashboard/departments/add/',      views.admin_department_add,  name='admin_department_add'),

    # Phase 4.3: Leave Management
    path('admin-dashboard/leaves/',                            views.admin_leave_list,   name='admin_leaves'),
    path('admin-dashboard/leaves/<int:leave_id>/<str:action>/',views.admin_leave_action, name='admin_leave_action'),

    # Phase 4.4 & 4.5: Attendance & Announcements
    path('admin-dashboard/attendance/',       views.admin_attendance,     name='admin_attendance'),
    path('admin-dashboard/announcements/',    views.admin_announcements,  name='admin_announcements'),

    # Phase 6: Payroll Management (Admin)
    path('admin-dashboard/payroll/',                      views.admin_payroll_list,   name='admin_payroll'),
    path('admin-dashboard/payroll/add/',                  views.admin_payroll_add,    name='admin_payroll_add'),
    path('admin-dashboard/payroll/download/<int:p_id>/',  views.admin_download_payslip, name='admin_download_payslip'),

    # Phase 7: History & Employee Detail
    path('employee-dashboard/history/',                   views.employee_history,               name='employee_history'),
    path('admin-dashboard/employees/<int:emp_id>/',       views.admin_employee_detail,          name='admin_employee_detail'),
    path('admin-dashboard/attendance/<int:att_id>/edit/', views.admin_employee_edit_attendance, name='admin_edit_attendance'),
    path('admin-dashboard/employees/<int:emp_id>/status/<str:action>/', views.admin_status_action, name='admin_status_action'),

    # Notifications
    path('notifications/mark-read/<int:notification_id>/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
]