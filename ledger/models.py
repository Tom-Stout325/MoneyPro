from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from core.models import Business, BusinessOwnedModelMixin


class Category(BusinessOwnedModelMixin):
    class CategoryType(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    class ScheduleCLine(models.TextChoices):
        # -------------------------
        # Part I — Income
        # -------------------------
        GROSS_RECEIPTS = "gross_receipts", "1"
        RETURNS_ALLOWANCES = "returns_allowances", "2"

        # -------------------------
        # Part II — Expenses
        # -------------------------
        ADVERTISING = "advertising", "8"
        CAR_TRUCK = "car_truck", "9"
        COMMISSIONS_FEES = "commissions_fees", "10"
        CONTRACT_LABOR = "contract_labor", "11"
        DEPLETION = "depletion", "12"
        DEPRECIATION = "depreciation", "13"
        EMPLOYEE_BENEFITS = "employee_benefits", "14"
        INSURANCE = "insurance", "15"
        INTEREST_MORTGAGE = "interest_mortgage", "16a"
        INTEREST_OTHER = "interest_other", "16b"
        LEGAL_PRO = "legal_pro", "17"
        OFFICE = "office", "18"
        PENSION_PROFIT = "pension_profit_sharing", "19"
        RENT_LEASE_VEHICLES = "rent_lease_vehicles", "20a"
        RENT_LEASE_OTHER = "rent_lease_other", "20b"
        REPAIRS = "repairs", "21"
        SUPPLIES = "supplies", "22"
        TAXES_LICENSES = "taxes_licenses", "23"
        TRAVEL = "travel", "24a"
        MEALS = "meals", "24b"
        UTILITIES = "utilities", "25"
        WAGES = "wages", "26"
        ENERGY_EFFICIENT = "energy_efficient_buildings", "27a"

        # -------------------------
        # Part V — Other expenses
        # -------------------------
        OTHER_EXPENSES_V = "other_expenses_part_v", "27b"

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=120, blank=True)
    category_type = models.CharField(max_length=10, choices=CategoryType.choices)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    # Visibility flags for reports
    book_reports = models.BooleanField(default=True)
    tax_reports = models.BooleanField(default=True)

    schedule_c_line = models.CharField(
        max_length=30,
        choices=ScheduleCLine.choices,
        blank=True,
        default="",
    )
    report_group = models.CharField(max_length=60, blank=True, default="")

    class Meta:
        ordering = ["category_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name", "category_type"],
                name="uniq_category_business_name_type",
            ),
            models.UniqueConstraint(
                fields=["business", "category_type", "slug"],
                name="uniq_category_business_type_slug",
            ),
        ]

    def clean(self):
        super().clean()
        if self.slug:
            self.slug = slugify(self.slug)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_category_type_display()}: {self.name}"




class SubCategory(BusinessOwnedModelMixin):
    class DeductionRule(models.TextChoices):
        FULL = "full", "100% deductible"
        MEALS_50 = "meals_50", "Meals (50%)"
        NONDEDUCTIBLE = "nondeductible", "Not deductible"

    class PayeeRole(models.TextChoices):
        ANY = "any", "Any"
        VENDOR = "vendor", "Vendor"
        CONTRACTOR = "contractor", "Contractor"
        CUSTOMER = "customer", "Customer"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="subcategories")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=140, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    book_enabled = models.BooleanField(default=True)
    tax_enabled = models.BooleanField(default=True)

    schedule_c_line = models.CharField(
        max_length=30,
        choices=Category.ScheduleCLine.choices,
        blank=True,
        default="",
        help_text="Optional override. If blank, reports may use Category.schedule_c_line.",
    )

    deduction_rule = models.CharField(
        max_length=20,
        choices=DeductionRule.choices,
        default=DeductionRule.FULL,
    )

    is_1099_reportable_default = models.BooleanField(default=False)
    is_capitalizable = models.BooleanField(default=False)

    requires_payee = models.BooleanField(default=False)
    payee_role = models.CharField(max_length=15, choices=PayeeRole.choices, default=PayeeRole.ANY)

    requires_transport = models.BooleanField(default=False)
    requires_vehicle = models.BooleanField(default=False)

    class Meta:
        ordering = ["category__category_type", "category__sort_order", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "category", "name"],
                name="uniq_subcategory_business_cat_name",
            ),
            models.UniqueConstraint(
                fields=["business", "slug"],
                condition=Q(slug__isnull=False) & ~Q(slug=""),
                name="uniq_subcategory_business_slug_nonblank",
            ),
        ]

    def clean(self):
        super().clean()

        # Tenant consistency: category must belong to same business
        if self.category_id and self.business_id and self.category.business_id != self.business_id:
            raise ValidationError({"category": "Category does not belong to this business."})

        if self.slug:
            self.slug = slugify(self.slug)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.category.name}-{self.name}" if self.category_id else self.name
            self.slug = slugify(base)
        self.full_clean()
        return super().save(*args, **kwargs)

    def effective_schedule_c_line(self) -> str:
        return self.schedule_c_line or (self.category.schedule_c_line if self.category_id else "")

    def __str__(self) -> str:
        return f"{self.category.name} → {self.name}"

    def is_book_visible(self) -> bool:
        return self.book_enabled and self.category.book_reports

    def is_tax_visible(self) -> bool:
        return self.tax_enabled and self.category.tax_reports





class Payee(BusinessOwnedModelMixin):
    display_name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    business_name = models.CharField(max_length=255, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    address1 = models.CharField(max_length=255, blank=True)
    address2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=50, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=50, blank=True, default="US")

    is_vendor = models.BooleanField(default=True)
    is_customer = models.BooleanField(default=False)
    is_contractor = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "display_name"],
                name="uniq_payee_display_name_per_business",
            )
        ]

    def __str__(self) -> str:
        return self.display_name




class PayeeTaxProfile(BusinessOwnedModelMixin):
    """Tax/compliance information for payees.

    Prefer W-9 PDF + last4, not full TIN storage.
    """

    ENTITY_CHOICES = [
        ("individual", "Individual / Sole Proprietor"),
        ("llc", "LLC"),
        ("partnership", "Partnership"),
        ("c_corp", "C Corporation"),
        ("s_corp", "S Corporation"),
        ("other", "Other"),
    ]
    W9_STATUS = [
        ("missing", "Missing"),
        ("requested", "Requested"),
        ("received", "Received"),
        ("verified", "Verified"),
    ]

    payee = models.OneToOneField(Payee, on_delete=models.CASCADE, related_name="tax_profile")

    is_1099_eligible = models.BooleanField(default=False)
    entity_type = models.CharField(max_length=25, choices=ENTITY_CHOICES, blank=True)

    TIN_CHOICES = [("ssn", "SSN"), ("ein", "EIN")]
    tin_type = models.CharField(max_length=10, choices=TIN_CHOICES, blank=True)
    tin_last4 = models.CharField(max_length=4, blank=True)

    w9_status = models.CharField(max_length=15, choices=W9_STATUS, default="missing")
    w9_document = models.FileField(upload_to="w9/", blank=True, null=True)

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "payee"], name="uniq_taxprofile_payee_per_business"),
        ]

    def clean(self):
        super().clean()
        if self.payee_id and self.business_id and self.payee.business_id != self.business_id:
            raise ValidationError({"payee": "Payee does not belong to this business."})





class Job(BusinessOwnedModelMixin):
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(default=timezone.now().year)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-year", "title"]
        constraints = [
            models.UniqueConstraint(fields=["business", "year", "title"], name="uniq_job_business_year_title")
        ]

    def __str__(self) -> str:
        return f"{self.year} • {self.title}"






class Transaction(BusinessOwnedModelMixin):
    TRANSPORT_CHOICES = [
        ("", "—"),
        ("personal_vehicle", "Personal vehicle"),
        ("rental_car", "Rental car"),
        ("business_vehicle", "Business vehicle"),
    ]

    date              = models.DateField(default=timezone.now)
    amount            = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    description       = models.CharField(max_length=255)
    subcategory       = models.ForeignKey(SubCategory, on_delete=models.PROTECT, related_name="transactions")
    category          = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="transactions", editable=False)
    payee             = models.ForeignKey(Payee, on_delete=models.PROTECT, related_name="transactions", null=True, blank=True)
    job               = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="transactions", null=True, blank=True)
    invoice_number    = models.CharField(max_length=25, blank=True)
    transport_type    = models.CharField(max_length=20, choices=TRANSPORT_CHOICES, blank=True, default="")
    vehicle           = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT, related_name="transactions", null=True, blank=True,)
    notes             = models.TextField(blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def clean(self):
        super().clean()

        # -------------------------
        # Tenant consistency checks
        # -------------------------
        if self.subcategory_id and self.business_id and self.subcategory.business_id != self.business_id:
            raise ValidationError({"subcategory": "Subcategory does not belong to this business."})

        if self.category_id and self.business_id and self.category.business_id != self.business_id:
            raise ValidationError({"category": "Category does not belong to this business."})

        if self.payee_id and self.business_id and self.payee.business_id != self.business_id:
            raise ValidationError({"payee": "Payee does not belong to this business."})

        if self.job_id and self.business_id and self.job.business_id != self.business_id:
            raise ValidationError({"job": "Job does not belong to this business."})

        if self.vehicle_id and self.business_id and self.vehicle.business_id != self.business_id:
            raise ValidationError({"vehicle": "Vehicle does not belong to this business."})

        # -------------------------
        # Auto category consistency
        # -------------------------
        if self.subcategory_id:
            expected = self.subcategory.category_id
            if self.category_id and self.category_id != expected:
                raise ValidationError({"category": "Category must match the selected subcategory."})

        # -------------------------
        # Amount validation
        # -------------------------
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": "Amount must be positive."})

        if not self.subcategory_id:
            return

        sc = self.subcategory

        # Payee rules
        if sc.requires_payee and not self.payee_id:
            raise ValidationError({"payee": "This subcategory requires a payee."})

        role = sc.payee_role or "any"
        if self.payee_id and role != "any":
            if role == "contractor" and not self.payee.is_contractor:
                raise ValidationError({"payee": "Select a payee marked as a contractor."})
            if role == "vendor" and not self.payee.is_vendor:
                raise ValidationError({"payee": "Select a payee marked as a vendor."})
            if role == "customer" and not self.payee.is_customer:
                raise ValidationError({"payee": "Select a payee marked as a customer."})

        # Transport + Vehicle rules
        if sc.requires_transport:
            if not self.transport_type:
                raise ValidationError({"transport_type": "Select a transport type."})

            valid = {"personal_vehicle", "rental_car", "business_vehicle"}
            if self.transport_type not in valid:
                raise ValidationError({"transport_type": "Invalid transport type."})

            if self.transport_type == "business_vehicle":
                if not self.vehicle_id:
                    raise ValidationError({"vehicle": "Select a business vehicle."})
            else:
                if self.vehicle_id:
                    raise ValidationError({"vehicle": "Remove vehicle; only used for business vehicles."})
        else:
            if self.transport_type:
                raise ValidationError({"transport_type": "Remove transport type; it is not needed for this subcategory."})
            if self.vehicle_id:
                raise ValidationError({"vehicle": "Remove vehicle; it is not needed for this subcategory."})

        if sc.requires_vehicle and not self.vehicle_id:
            raise ValidationError({"vehicle": "Select a vehicle for this subcategory."})

    def save(self, *args, **kwargs):
        if self.subcategory_id:
            self.category = self.subcategory.category
        self.full_clean()
        return super().save(*args, **kwargs)
