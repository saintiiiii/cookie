from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.template import loader
from django.utils import timezone

from bakery.models import ActivityLog, Category, EmployeeSecurity, InventoryLog, Order, Product, ProductionBatch, Supplier
from bakery.services import ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY, generate_product_barcode, generate_product_sku, generate_temporary_password, log_activity
from bakery.utils.http import client_ip


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            base_class = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{base_class} form-check-input".strip()
            else:
                widget.attrs["class"] = f"{base_class} form-control".strip()


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))


class PasswordResetRequestForm(StyledFormMixin, PasswordResetForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "Email address"}))

    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.html",
        use_https=False,
        token_generator=None,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        email = self.cleaned_data["email"]
        for user in self.get_users(email):
            temporary_password = generate_temporary_password()
            user.set_password(temporary_password)
            user.save(update_fields=["password"])
            EmployeeSecurity.objects.update_or_create(
                user=user,
                defaults={
                    "must_change_password": True,
                    "temporary_password_created_at": timezone.now(),
                    "temporary_password_set_by": None,
                },
            )
            context = {
                "email": user.email,
                "user": user,
                "temporary_password": temporary_password,
                **(extra_email_context or {}),
            }
            subject = loader.render_to_string(subject_template_name, context)
            subject = "".join(subject.splitlines())
            body = loader.render_to_string(email_template_name, context)
            send_mail(subject, body, from_email, [user.email])
            log_activity(
                action=ActivityLog.ACTION_PASSWORD,
                instance=user,
                description="Generated temporary password from forgot-password email request.",
                ip_address=client_ip(request),
            )


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "barcode_prefix", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["barcode_prefix"].required = False
        self.fields["color"].required = False


class ProductForm(StyledFormMixin, forms.ModelForm):
    auto_generate_sku = forms.BooleanField(required=False, initial=True)
    auto_generate_barcode = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = Product
        fields = [
            "item_id",
            "name",
            "description",
            "category",
            "supplier",
            "sku",
            "barcode",
            "price",
            "cost",
            "stock_quantity",
            "low_stock_threshold",
            "production_date",
            "expiry_date",
            "theme_color",
            "storage_location",
            "product_image",
            "is_active",
            "is_archived",
        ]
        labels = {"cost": "Cost Price", "price": "Unit Price", "item_id": "Item ID"}
        widgets = {
            "production_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "theme_color": forms.TextInput(attrs={"type": "color"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        is_create = not self.instance.pk
        self.fields["auto_generate_sku"].initial = is_create
        self.fields["auto_generate_barcode"].initial = is_create
        self.fields["item_id"].required = False
        self.fields["sku"].required = not is_create
        self.fields["barcode"].required = not is_create
        self.fields["auto_generate_sku"].help_text = "Uses the selected category prefix, for example BRD-0001."
        self.fields["auto_generate_barcode"].help_text = "Generates a unique printable barcode value."

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        if category:
            if cleaned_data.get("auto_generate_sku") or not cleaned_data.get("sku"):
                cleaned_data["sku"] = generate_product_sku(category)
            if cleaned_data.get("auto_generate_barcode") or not cleaned_data.get("barcode"):
                cleaned_data["barcode"] = generate_product_barcode(category)
        if not cleaned_data.get("sku"):
            self.add_error("sku", "SKU is required unless auto-generate is enabled.")
        if not cleaned_data.get("barcode"):
            self.add_error("barcode", "Barcode is required unless auto-generate is enabled.")
        production_date = cleaned_data.get("production_date")
        expiry_date = cleaned_data.get("expiry_date")
        if production_date and expiry_date and expiry_date < production_date:
            self.add_error("expiry_date", "Expiry date cannot be earlier than production date.")
        return cleaned_data


class SupplierForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "notes"]


class OrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "customer_name",
            "contact",
            "product",
            "order_date",
            "pickup_date",
            "quantity",
            "estimated_total",
            "notes",
            "status",
        ]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "pickup_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ProductionBatchForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProductionBatch
        fields = [
            "product",
            "batch_number",
            "production_date",
            "expiry_date",
            "quantity_produced",
            "quantity_remaining",
            "notes",
        ]
        widgets = {
            "production_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        produced = cleaned_data.get("quantity_produced")
        remaining = cleaned_data.get("quantity_remaining")
        production_date = cleaned_data.get("production_date")
        expiry_date = cleaned_data.get("expiry_date")
        if produced and remaining and remaining > produced:
            self.add_error("quantity_remaining", "Remaining quantity cannot exceed produced quantity.")
        if production_date and expiry_date and expiry_date < production_date:
            self.add_error("expiry_date", "Expiry date cannot be earlier than production date.")
        return cleaned_data


class StockMovementFormMixin(StyledFormMixin, forms.Form):
    MOVEMENT_INCREASE = "increase"
    MOVEMENT_DECREASE = "decrease"
    MOVEMENT_CHOICES = [
        (MOVEMENT_INCREASE, "Increase"),
        (MOVEMENT_DECREASE, "Decrease"),
    ]

    movement = forms.ChoiceField(choices=MOVEMENT_CHOICES, required=False)
    reason = forms.ChoiceField(choices=InventoryLog.REASON_CHOICES, required=False)
    note = forms.CharField(required=False)

    def clean_movement(self):
        return self.cleaned_data.get("movement") or self.MOVEMENT_INCREASE

    def clean(self):
        cleaned_data = super().clean()
        movement = cleaned_data.get("movement") or self.MOVEMENT_INCREASE
        reason = cleaned_data.get("reason")
        if movement == self.MOVEMENT_DECREASE and not reason:
            self.add_error("reason", "A deduction reason is required.")
        if movement == self.MOVEMENT_INCREASE and not reason:
            cleaned_data["reason"] = InventoryLog.REASON_RESTOCK
        return cleaned_data

    def signed_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self.cleaned_data["movement"] == self.MOVEMENT_DECREASE:
            return -quantity
        return quantity


class RestockProductForm(StockMovementFormMixin):
    quantity = forms.IntegerField(min_value=1)


class PasswordSecurityMixin:
    password_help = "Use at least 8 characters with uppercase, lowercase, number, and special character. Example: Example@123"

    def validate_password_format(self, value):
        errors = []
        if len(value) < 8:
            errors.append("Password must be at least 8 characters.")
        if not any(character.isupper() for character in value):
            errors.append("Password must contain an uppercase letter.")
        if not any(character.islower() for character in value):
            errors.append("Password must contain a lowercase letter.")
        if not any(character.isdigit() for character in value):
            errors.append("Password must contain a number.")
        if not any(not character.isalnum() for character in value):
            errors.append("Password must contain a special character.")
        if errors:
            raise ValidationError(errors)
        return value


class EmployeeCreateForm(PasswordSecurityMixin, StyledFormMixin, UserCreationForm):
    role = forms.ChoiceField(choices=[(ROLE_ADMIN, ROLE_ADMIN), (ROLE_CASHIER, ROLE_CASHIER), (ROLE_INVENTORY, ROLE_INVENTORY)])

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = self.password_help
        self.fields["password2"].help_text = "Enter the same password again."

    def clean_password1(self):
        return self.validate_password_format(self.cleaned_data["password1"])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            user.save()
            group = Group.objects.get(name=self.cleaned_data["role"])
            user.groups.set([group])
        return user


class EmployeeUpdateForm(StyledFormMixin, forms.ModelForm):
    role = forms.ChoiceField(choices=[(ROLE_ADMIN, ROLE_ADMIN), (ROLE_CASHIER, ROLE_CASHIER), (ROLE_INVENTORY, ROLE_INVENTORY)])

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_group = self.instance.groups.filter(name__in=[ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY]).first()
        if current_group:
            self.fields["role"].initial = current_group.name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            user.save()
            group = Group.objects.get(name=self.cleaned_data["role"])
            user.groups.set([group])
        return user


class AdminPasswordResetForm(PasswordSecurityMixin, StyledFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].help_text = self.password_help
        self.fields["new_password2"].help_text = "Enter the same password again."

    def clean_new_password1(self):
        return self.validate_password_format(self.cleaned_data["new_password1"])


class SecureSetPasswordForm(AdminPasswordResetForm):
    pass


class TemporaryPasswordResetForm(StyledFormMixin, forms.Form):
    confirm = forms.BooleanField(
        label="Generate a temporary password and require a password change on next login",
        required=True,
    )


class VoidSaleForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), min_length=5)
