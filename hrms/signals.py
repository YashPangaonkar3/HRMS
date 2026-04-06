from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Leave, Notification, User


@receiver(pre_save, sender=Leave)
def leave_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
        instance._previous_status = previous.status
    except sender.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Leave)
def leave_post_save(sender, instance, created, **kwargs):
    if created:
        admins = User.objects.filter(role='admin', status='approved')
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                actor=instance.employee,
                message=(
                    f"New leave request from {instance.employee.get_full_name()} "
                    f"({instance.employee.username}) for {instance.duration_days or 0} day(s)."
                )
            )
        return

    old_status = getattr(instance, '_previous_status', None)
    new_status = instance.status
    if old_status == new_status:
        return

    if new_status == 'approved':
        Notification.objects.create(
            recipient=instance.employee,
            actor=instance.reviewed_by,
            message=(
                f"Your leave request (ID: {instance.id}) has been approved by "
                f"{(instance.reviewed_by.get_full_name() or instance.reviewed_by.username) if instance.reviewed_by else 'an admin'}."
            )
        )
    elif new_status == 'rejected':
        Notification.objects.create(
            recipient=instance.employee,
            actor=instance.reviewed_by,
            message=(
                f"Your leave request (ID: {instance.id}) has been rejected by "
                f"{(instance.reviewed_by.get_full_name() or instance.reviewed_by.username) if instance.reviewed_by else 'an admin'}."
            )
        )
    elif new_status == 'cancel_requested' and old_status in ['pending', 'approved']:
        admins = User.objects.filter(role='admin', status='approved')
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                actor=instance.employee,
                message=(
                    f"Cancellation request for leave (ID: {instance.id}) from "
                    f"{instance.employee.get_full_name()} ({instance.employee.username})."
                )
            )
    elif new_status == 'cancelled':
        Notification.objects.create(
            recipient=instance.employee,
            actor=instance.cancellation_reviewed_by,
            message=(
                f"Your leave cancellation request (ID: {instance.id}) has been approved by "
                f"{(instance.cancellation_reviewed_by.get_full_name() or instance.cancellation_reviewed_by.username) if instance.cancellation_reviewed_by else 'an admin'}."
            )
        )
    elif old_status == 'cancel_requested' and new_status in ['pending', 'approved', 'rejected']:
        Notification.objects.create(
            recipient=instance.employee,
            actor=instance.cancellation_reviewed_by,
            message=(
                f"Your leave cancellation request (ID: {instance.id}) was rejected by "
                f"{(instance.cancellation_reviewed_by.get_full_name() or instance.cancellation_reviewed_by.username) if instance.cancellation_reviewed_by else 'an admin'}."
            )
        )
