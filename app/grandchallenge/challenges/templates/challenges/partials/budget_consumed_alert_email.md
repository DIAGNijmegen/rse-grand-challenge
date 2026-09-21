{% load costs url %}
We would like to inform you that more than {{ percent_threshold }}%
of the compute budget for {{ invoice.get_payment_type_display }} invoice {{ invoice_name }}
of the {{ challenge.short_name }} challenge has been used.

{% if challenge.percent_active_compute_budget_remaining %}
Your challenge still has {{ challenge.percent_active_compute_budget_remaining }}% of its total budget available and **has not been closed**.
Your challenge's remaining compute budget is {{ challenge.active_available_compute_cost_euro_millicents|millicents_to_euro }}.
{% else %}
Your challenge has now consumed its entire budget and **has been closed**.
{% endif %}

For more information please see the [challenge's invoice page]({% url 'invoices:list' challenge_short_name=challenge.short_name %}) or reply to this email.
