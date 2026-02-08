from django.conf import settings
from django.db import models


class CompanyProfile(models.Model):
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_profile",)

    # Identity
    company_name     = models.CharField(max_length=120)
    legal_name       = models.CharField(max_length=120, blank=True)
    ein              = models.CharField(max_length=15, blank=True, help_text="Federal EIN (XX-XXXXXXX)",)

    # Contact
    phone            = models.CharField(max_length=30, blank=True)
    billing_email    = models.EmailField(blank=True)

    # Address
    address_line1    = models.CharField(max_length=120, blank=True)
    address_line2    = models.CharField(max_length=120, blank=True)
    city             = models.CharField(max_length=80, blank=True)
    state            = models.CharField(max_length=50, blank=True)
    postal_code      = models.CharField(max_length=20, blank=True)
    country          = models.CharField(max_length=50, default="US")

    # Branding
    logo             = models.ImageField(upload_to="company_logos/", blank=True, null=True)

    # Locale / formatting
    timezone         = models.CharField(max_length=64, default="America/Indiana/Indianapolis",)
    currency         = models.CharField(max_length=10, default="USD")

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name or f"CompanyProfile for {self.user}"

    @property
    def is_complete(self) -> bool:
        # v1 strict: company name only
        return bool(self.company_name.strip())

    @property
    def phone_display(self) -> str:
        p = (self.phone or "").strip()
        if p.isdigit() and len(p) == 10:
            return f"({p[:3]}){p[3:6]}-{p[6:]}"
        return p