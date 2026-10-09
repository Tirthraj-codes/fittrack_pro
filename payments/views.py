from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, member_required

from .forms import CheckoutForm, ManualPaymentForm, MarkPaidForm
from .models import STATUS_LABELS, Payment
from .receipts import build_receipt
from .services import mark_paid


def _total(queryset):
    return queryset.aggregate(total=Sum('amount'))['total'] or 0


def _form_page(request, form, title, subtitle, submit_label, cancel_url_name,
               icon='bi-cash-coin', icon_class='grad-teal'):
    """Reuses the shared form page from the memberships templates."""
    return render(request, 'memberships/form.html', {
        'form': form, 'title': title, 'subtitle': subtitle,
        'submit_label': submit_label, 'cancel_url': reverse(cancel_url_name),
        'icon': icon, 'icon_class': icon_class,
    })


def _check_access(request, payment):
    """A member may only see their own payment. Admins may see any."""
    if payment.member_id != request.user.pk and not request.user.is_admin_role:
        raise PermissionDenied


# ================= Member =================
@member_required
def my_payments(request):
    payments = request.user.payments.select_related('membership')
    unpaid = payments.filter(status=Payment.Status.PENDING)
    context = {
        'payments': payments,
        'total_paid': _total(payments.paid()),
        'amount_due': _total(unpaid),
        'due_count': unpaid.count(),
        'overdue_count': payments.overdue().count(),
    }
    return render(request, 'payments/my_payments.html', context)


@member_required
def checkout(request, pk):
    payment = get_object_or_404(Payment, pk=pk, member=request.user)
    if payment.status != Payment.Status.PENDING:
        messages.info(request, 'This payment is not waiting to be paid.')
        return redirect('my_payments')

    form = CheckoutForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        mark_paid(payment, form.cleaned_data['method'])
        return redirect('payment_success', pk=payment.pk)
    return render(request, 'payments/checkout.html', {'form': form, 'payment': payment})


@login_required
def success(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('member', 'membership'), pk=pk)
    _check_access(request, payment)
    if payment.status != Payment.Status.PAID:
        return redirect('my_payments' if request.user.is_member else 'payment_list')
    return render(request, 'payments/success.html', {'payment': payment})


@login_required
def receipt_pdf(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('member', 'membership'), pk=pk)
    _check_access(request, payment)
    if payment.status != Payment.Status.PAID:
        raise Http404('Receipts exist only for paid payments.')
    response = HttpResponse(build_receipt(payment), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{payment.receipt_no}.pdf"'
    return response


# ================= Admin =================
@admin_required
def payment_list(request):
    status = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()
    today = timezone.localdate()

    payments = Payment.objects.select_related('member', 'membership')
    if status in STATUS_LABELS:
        payments = getattr(payments, status)()          # e.g. payments.overdue()
    if q:
        payments = payments.filter(
            Q(member__username__icontains=q) | Q(member__first_name__icontains=q)
            | Q(member__last_name__icontains=q) | Q(description__icontains=q)
            | Q(transaction_id__icontains=q) | Q(receipt_no__icontains=q)
        )

    chips = [
        {'key': key, 'label': label, 'count': getattr(Payment.objects, key)().count()}
        for key, label in STATUS_LABELS.items()
    ]
    collected = _total(Payment.objects.paid().filter(paid_on__year=today.year, paid_on__month=today.month))
    context = {
        'payments': payments, 'status': status, 'q': q, 'chips': chips,
        'total': Payment.objects.count(),
        'collected_this_month': collected,
        'unpaid_total': _total(Payment.objects.filter(status=Payment.Status.PENDING)),
        'overdue_count': Payment.objects.overdue().count(),
    }
    return render(request, 'payments/payment_list.html', context)


@admin_required
def payment_mark_paid(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('member'), pk=pk)
    if payment.status != Payment.Status.PENDING:
        messages.error(request, 'Only a pending payment can be marked as paid.')
        return redirect('payment_list')

    form = MarkPaidForm(request.POST or None, initial={'method': Payment.Method.CASH})
    if request.method == 'POST' and form.is_valid():
        mark_paid(payment, form.cleaned_data['method'], by=request.user, note=form.cleaned_data['note'])
        messages.success(
            request,
            f'Payment of ₹{payment.amount:,.0f} from {payment.member.display_name} recorded. Receipt {payment.receipt_no}.'
        )
        return redirect('payment_list')

    subtitle = f'{payment.member.display_name}: {payment.description}, ₹{payment.amount:,.0f}'
    return _form_page(request, form, 'Mark as paid', subtitle, 'Record payment', 'payment_list',
                      'bi-check2-circle', 'grad-teal')


@admin_required
def payment_create(request):
    form = ManualPaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        payment = Payment.objects.create(
            member=data['member'], description=data['description'],
            amount=data['amount'], due_date=data['due_date'],
        )
        if data['already_paid']:
            mark_paid(payment, data['method'], by=request.user)
        messages.success(request, f'Payment added for {data["member"].display_name}.')
        return redirect('payment_list')
    return _form_page(request, form, 'Add a payment', 'For extra charges that are not part of a membership.',
                      'Add payment', 'payment_list', 'bi-plus-circle-fill', 'grad-orange')


@admin_required
@require_POST
def payment_cancel(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('member'), pk=pk)
    if payment.status == Payment.Status.PENDING:
        payment.status = Payment.Status.CANCELLED
        payment.save(update_fields=['status'])
        messages.success(request, f'Payment "{payment.description}" for {payment.member.display_name} was cancelled.')
    else:
        messages.error(request, 'Only a pending payment can be cancelled.')
    return redirect('payment_list')