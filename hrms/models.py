from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


# ─── Model 1: Department ───────────────────────────────────────────
class Department(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ─── Model 2: Custom User ──────────────────────────────────────────
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin',    'Admin'),
        ('employee', 'Employee'),
    ]
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    role            = models.CharField(max_length=10, choices=ROLE_CHOICES, default='employee')
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    employee_id     = models.CharField(max_length=20, unique=True, blank=True, null=True)
    phone           = models.CharField(max_length=15, blank=True, null=True)
    address         = models.TextField(blank=True, null=True)
    date_of_birth   = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    department           = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    designation          = models.CharField(max_length=100, blank=True, null=True)
    date_joined          = models.DateField(blank=True, null=True)
    bank_name            = models.CharField(max_length=120, blank=True, null=True)
    pan_number           = models.CharField(max_length=50, blank=True, null=True)
    account_number       = models.CharField(max_length=50, blank=True, null=True)
    monthly_leave_quota  = models.PositiveIntegerField(default=2, help_text='Monthly leave quota assigned by admin.')

    def get_monthly_leave_used(self, year=None, month=None):
        from django.utils import timezone
        now = timezone.localtime(timezone.now())
        year = year or now.year
        month = month or now.month
        leaves = self.leaves.filter(status__in=['pending', 'approved'], start_date__year=year, start_date__month=month)
        total = sum(l.duration_days or 0 for l in leaves)
        return total

    def get_monthly_leave_remaining(self, year=None, month=None):
        used = self.get_monthly_leave_used(year=year, month=month)
        remaining = self.monthly_leave_quota - used
        return max(remaining, 0)

    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"


# ─── Model 3: Leave ────────────────────────────────────────────────
class Leave(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('sick',   'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('annual', 'Annual Leave'),
        ('unpaid', 'Unpaid Leave'),
    ]
    STATUS_CHOICES = [
        ('pending',          'Pending'),
        ('approved',         'Approved'),
        ('rejected',         'Rejected'),
        ('cancel_requested', 'Cancel Requested'),
        ('cancelled',        'Cancelled'),
    ]

    employee    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
    leave_type  = models.CharField(max_length=10, choices=LEAVE_TYPE_CHOICES)
    start_date  = models.DateField()
    end_date    = models.DateField()
    reason      = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_on  = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leaves')
    reviewed_on = models.DateTimeField(null=True, blank=True)
    cancellation_requested_on = models.DateTimeField(null=True, blank=True)
    cancellation_reviewed_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancellation_reviewed_leaves')
    cancellation_reviewed_on  = models.DateTimeField(null=True, blank=True)
    cancellation_original_status = models.CharField(max_length=20, null=True, blank=True, choices=STATUS_CHOICES)

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError('Leave end date must be on or after start date.')

    @property
    def duration_days(self):
        if self.end_date and self.start_date:
            if self.end_date < self.start_date:
                return None
            return (self.end_date - self.start_date).days + 1
        return None

    def can_request_cancellation(self, limit_minutes=15):
        from django.utils import timezone
        from datetime import timedelta

        if self.status not in ['pending', 'approved']:
            return False

        if self.cancellation_requested_on:
            return False

        if not self.applied_on:
            return False

        if timezone.localtime(timezone.now()) <= self.applied_on + timedelta(minutes=limit_minutes):
            return True

        return False

    def request_cancellation(self):
        from django.utils import timezone

        if not self.can_request_cancellation():
            raise ValidationError('Cancellation request is not allowed at this time.')

        self.cancellation_original_status = self.status
        self.status = 'cancel_requested'
        self.cancellation_requested_on = timezone.localtime(timezone.now())
        self.save()

    @property
    def cancellation_eligible(self):
        return self.can_request_cancellation()

    def approve_cancellation(self, reviewer):
        from django.utils import timezone

        if self.status != 'cancel_requested':
            raise ValidationError('Only cancellation requests can be approved.')

        self.status = 'cancelled'
        self.cancellation_reviewed_by = reviewer
        self.cancellation_reviewed_on = timezone.localtime(timezone.now())
        self.save()

    def reject_cancellation(self, reviewer):
        from django.utils import timezone

        if self.status != 'cancel_requested':
            raise ValidationError('Only cancellation requests can be rejected.')

        self.status = self.cancellation_original_status or 'pending'
        self.cancellation_reviewed_by = reviewer
        self.cancellation_reviewed_on = timezone.localtime(timezone.now())
        self.cancellation_original_status = None
        self.cancellation_requested_on = None
        self.save()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.username} - {self.leave_type} ({self.status})"





# ─── Model 3.5: Notification ───────────────────────────────────────
class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications_sent')
    message   = models.CharField(max_length=260)
    is_read   = models.BooleanField(default=False)
    created_at= models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])

    def __str__(self):
        return f"Notification -> {self.recipient.username}: {self.message[:50]}"


# ─── Model 4: Attendance ───────────────────────────────────────────
class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present',  'Present'),
        ('absent',   'Absent'),
        ('half_day', 'Half Day'),
        ('late',     'Late'),
    ]
    ADDED_BY_CHOICES = [
        ('self',  'Self'),
        ('admin', 'Admin'),
    ]

    employee  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    date      = models.DateField()
    clock_in  = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    status    = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    added_by  = models.CharField(max_length=5, choices=ADDED_BY_CHOICES, default='self')

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.username} - {self.date} ({self.status})"


# ─── Model 5: Payroll ──────────────────────────────────────────────
class Payroll(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid',    'Paid'),
    ]

    employee      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payrolls')
    month         = models.IntegerField()
    year          = models.IntegerField()
    basic_salary  = models.DecimalField(max_digits=12, decimal_places=2)
    allowances    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary    = models.DecimalField(max_digits=12, decimal_places=2, blank=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_date  = models.DateField(null=True, blank=True)
    generated_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_payrolls')

    def save(self, *args, **kwargs):
        # Auto-calculate net salary before saving
        self.net_salary = self.basic_salary + self.allowances - self.deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.username} - {self.month}/{self.year} ({self.status})"


# ─── Model 6: Announcement ─────────────────────────────────────────
class Announcement(models.Model):
    title      = models.CharField(max_length=200)
    content    = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    def __str__(self):
        return self.title