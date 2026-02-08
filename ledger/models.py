from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Q

from core.models import OwnedModelMixin





class Category(OwnedModelMixin):
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
    book_reports = models.BooleanField(default=True)
    tax_reports = models.BooleanField(default=True)
    schedule_c_line = models.CharField(max_length=30, choices=ScheduleCLine.choices, blank=True,default="",)
    report_group = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["category_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "category_type"],
                name="uniq_category_user_name_type",
            ),
            models.UniqueConstraint(
                fields=["user", "category_type", "slug"],
                name="uniq_category_user_type_slug",
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

    def __str__(self):
        return f"{self.get_category_type_display()}: {self.name}"


class SubCategory(OwnedModelMixin):
    class DeductionRule(models.TextChoices):
        FULL = "full", "100% deductible"
        MEALS_50 = "meals_50", "Meals (50%)"
        NONDEDUCTIBLE = "nondeductible", "Not deductible"
        # Future: partial/custom rules if needed

    class PayeeRole(models.TextChoices):
        ANY = "any", "Any"
        VENDOR = "vendor", "Vendor"
        CONTRACTOR = "contractor", "Contractor"
        CUSTOMER = "customer", "Customer"

    category           = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="subcategories")
    name               = models.CharField(max_length=80)
    slug               = models.SlugField(max_length=140, blank=True, null=True)

    is_active          = models.BooleanField(default=True)
    sort_order         = models.PositiveIntegerField(default=0)
    book_enabled       = models.BooleanField(default=True)
    tax_enabled        = models.BooleanField(default=True)

    schedule_c_line    = models.CharField(max_length=30, choices=Category.ScheduleCLine.choices, blank=True, default="", help_text="Optional override. If blank, reports may use Category.schedule_c_line.",)
    deduction_rule     = models.CharField(max_length=20, choices=DeductionRule.choices, default=DeductionRule.FULL)

    is_1099_reportable_default = models.BooleanField(default=False)


    is_capitalizable   = models.BooleanField(default=False)
    requires_payee     = models.BooleanField(default=False)
    payee_role         = models.CharField(max_length=15, choices=PayeeRole.choices, default=PayeeRole.ANY)

    requires_transport = models.BooleanField(default=False)  # personal vs rental
    requires_vehicle   = models.BooleanField(default=False)

    class Meta:
        ordering = ["category__category_type", "category__sort_order", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "name"],
                name="uniq_subcategory_user_cat_name",
            ),
            models.UniqueConstraint(
                fields=["user", "slug"],
                condition=Q(slug__isnull=False) & ~Q(slug=""),
                name="uniq_subcategory_user_slug_nonblank",
            ),
        ]

    def clean(self):
        super().clean()

        # Ownership enforcement
        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            raise ValidationError({"category": "Category does not belong to this user."})

        if self.slug:
            self.slug = slugify(self.slug)

    def save(self, *args, **kwargs):
        if not self.slug:
            # Include category in slug to reduce collisions
            base = f"{self.category.name}-{self.name}" if self.category_id else self.name
            self.slug = slugify(base)
        self.full_clean()
        return super().save(*args, **kwargs)

    def effective_schedule_c_line(self) -> str:
        """
        Subcategory mapping wins; otherwise category default.
        """
        return self.schedule_c_line or (self.category.schedule_c_line if self.category_id else "")

    def __str__(self):
        return f"{self.category.name} → {self.name}"

    def is_book_visible(self) -> bool:
        return self.book_enabled and self.category.book_enabled

    def is_tax_visible(self) -> bool:
        return self.tax_enabled and self.category.tax_enabled






class Transaction(OwnedModelMixin):
    
    TRANSPORT_CHOICES = [
        ("", "—"),
        ("personal_vehicle", "Personal vehicle"),
        ("rental_car", "Rental car"),
        ("business_vehicle", "Business vehicle"),
    ]
    
    
    date           = models.DateField(default=timezone.now)
    amount         = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    description    = models.CharField(max_length=255)
    subcategory    = models.ForeignKey(SubCategory, on_delete=models.PROTECT, related_name="transactions")
    category       = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="transactions", editable=False)
    payee          = models.ForeignKey("Payee", on_delete=models.PROTECT, related_name="transactions", null=True, blank=True)
    job            = models.ForeignKey("Job", on_delete=models.PROTECT, related_name="transactions", null=True, blank=True)
    invoice_number = models.CharField(max_length=25, blank=True)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_CHOICES, blank=True, default="")
    vehicle        = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT, related_name="transactions", null=True, blank=True,)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def clean(self):
        super().clean()

        # -------------------------
        # Ownership checks
        # -------------------------
        if self.subcategory_id and self.user_id and self.subcategory.user_id != self.user_id:
            raise ValidationError({"subcategory": "Subcategory does not belong to this user."})

        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            raise ValidationError({"category": "Category does not belong to this user."})

        if self.payee_id and self.user_id and self.payee.user_id != self.user_id:
            raise ValidationError({"payee": "Payee does not belong to this user."})

        if self.job_id and self.user_id and self.job.user_id != self.user_id:
            raise ValidationError({"job": "Job does not belong to this user."})
        
        if self.vehicle_id and self.user_id and self.vehicle.user_id != self.user_id:
            raise ValidationError({"vehicle": "Vehicle does not belong to this user."})

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

        # -------------------------
        # SubCategory-driven rules (NO name matching)
        # -------------------------
        if not self.subcategory_id:
            return

        sc = self.subcategory  # expects: requires_payee, payee_role, requires_transport, requires_vehicle

        # Payee rules
        if getattr(sc, "requires_payee", False) and not self.payee_id:
            raise ValidationError({"payee": "This subcategory requires a payee."})

        # Role rules (only enforce if payee present AND role not 'any')
        role = getattr(sc, "payee_role", "any") or "any"
        if self.payee_id and role != "any":
            if role == "contractor" and not self.payee.is_contractor:
                raise ValidationError({"payee": "Select a payee marked as a contractor."})
            if role == "vendor" and not self.payee.is_vendor:
                raise ValidationError({"payee": "Select a payee marked as a vendor."})
            if role == "customer" and not self.payee.is_customer:
                raise ValidationError({"payee": "Select a payee marked as a customer."})

        # Transport + Vehicle rules (SubCategory-driven)
        # Expect:
        # - Transaction.transport_type choices now include: personal_vehicle, rental_car, business_vehicle
        # - Transaction.vehicle FK exists (nullable)
        # - SubCategory has: requires_transport, requires_vehicle

        if getattr(sc, "requires_transport", False):
            if not self.transport_type:
                raise ValidationError({"transport_type": "Select a transport type."})

            valid = {"personal_vehicle", "rental_car", "business_vehicle"}
            if self.transport_type not in valid:
                raise ValidationError({"transport_type": "Invalid transport type."})

            # If transport is business vehicle, a specific Vehicle must be selected
            if self.transport_type == "business_vehicle":
                if not self.vehicle_id:
                    raise ValidationError({"vehicle": "Select a business vehicle."})
            else:
                # Personal/Rental should not have a Vehicle FK selected
                if self.vehicle_id:
                    raise ValidationError({"vehicle": "Remove vehicle; only used for business vehicles."})

        else:
            # Subcategory does not require transport; enforce blank fields
            if self.transport_type:
                raise ValidationError(
                    {"transport_type": "Remove transport type; it is not needed for this subcategory."}
                )
            if self.vehicle_id:
                raise ValidationError({"vehicle": "Remove vehicle; it is not needed for this subcategory."})

        # Vehicle rules (only apply when subcategory explicitly requires a vehicle)
        # (This is independent from requires_transport; it lets you require a vehicle even if you later
        # have subcategories that need a vehicle without transport selection.)
        if getattr(sc, "requires_vehicle", False):
            if not self.vehicle_id:
                raise ValidationError({"vehicle": "Select a vehicle for this subcategory."})


    def save(self, *args, **kwargs):
        if self.subcategory_id:
            self.category = self.subcategory.category
        self.full_clean()
        return super().save(*args, **kwargs)





class Payee(OwnedModelMixin):
    display_name  = models.CharField(max_length=255)
    legal_name    = models.CharField(max_length=255, blank=True)
    business_name = models.CharField(max_length=255, blank=True)
    email         = models.EmailField(blank=True)
    phone         = models.CharField(max_length=50, blank=True)
    address1      = models.CharField(max_length=255, blank=True)
    address2      = models.CharField(max_length=255, blank=True)
    city          = models.CharField(max_length=120, blank=True)
    state         = models.CharField(max_length=50, blank=True)
    zip_code      = models.CharField(max_length=20, blank=True)
    country       = models.CharField(max_length=50, blank=True, default="US")
    is_vendor     = models.BooleanField(default=True)
    is_customer   = models.BooleanField(default=False)
    is_contractor = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "display_name"], name="uniq_payee_display_name_per_user"
            )
        ]

    def __str__(self) -> str:
        return self.display_name



class PayeeTaxProfile(OwnedModelMixin):
    """
    Tax / compliance information for payees. Keep sensitive data minimal.
    Prefer W-9 PDF + last4, not full TIN storage.
    """
    payee            = models.OneToOneField(Payee, on_delete=models.CASCADE, related_name="tax_profile")

    is_1099_eligible = models.BooleanField(default=False)

    ENTITY_CHOICES   = [
        ("individual", "Individual / Sole Proprietor"),
        ("llc", "LLC"),
        ("partnership", "Partnership"),
        ("c_corp", "C Corporation"),
        ("s_corp", "S Corporation"),
        ("other", "Other"),
    ]
    entity_type      = models.CharField(max_length=25, choices=ENTITY_CHOICES, blank=True)

    TIN_CHOICES      = [("ssn", "SSN"), ("ein", "EIN")]
    tin_type         = models.CharField(max_length=10, choices=TIN_CHOICES, blank=True)
    tin_last4        = models.CharField(max_length=4, blank=True)

    W9_STATUS = [
        ("missing", "Missing"),
        ("requested", "Requested"),
        ("received", "Received"),
        ("verified", "Verified"),
    ]
    w9_status        = models.CharField(max_length=15, choices=W9_STATUS, default="missing")
    w9_document      = models.FileField(upload_to="w9/", blank=True, null=True)

    notes            = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "payee"], name="uniq_taxprofile_payee_per_user")
        ]

    def clean(self):
        super().clean()
        if self.payee_id and self.user_id and self.payee.user_id != self.user_id:
            raise ValidationError({"payee": "Payee does not belong to this user."})




class Job(OwnedModelMixin):
    title             = models.CharField(max_length=255)
    year              = models.PositiveIntegerField(default=timezone.now().year)
    is_active         = models.BooleanField(default=True)

    class Meta:
        ordering = ["-year", "title"]
        constraints = [
            models.UniqueConstraint(fields=["user", "year", "title"], name="uniq_job_user_year_title")
        ]

    def __str__(self):
        return f"{self.year} • {self.title}"
