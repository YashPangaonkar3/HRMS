from .models import Notification


def notifications_context(request):
    if not request.user.is_authenticated:
        return {}

    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    recent_notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:6]

    return {
        'notification_unread_count': unread_count,
        'notifications': recent_notifications,
    }
