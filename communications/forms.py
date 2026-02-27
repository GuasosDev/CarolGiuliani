# forms.py

from django import forms
from .models import EmailAccount

class EmailAccountAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        label="Contraseña"
    )

    class Meta:
        model = EmailAccount
        exclude = ("encrypted_password",)

    def save(self, commit=True):
        instance = super().save(commit=False)

        password = self.cleaned_data.get("password")
        if password:
            instance.set_password(password)

        if commit:
            instance.save()

        return instance