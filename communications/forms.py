from django import forms
from .models import QuickReply
from clients.models import Client
from .models import EmailAccount

class QuickReplyForm(forms.ModelForm):
    class Meta:
        model = QuickReply
        fields = ['title', 'shortcut', 'content', 'channel', 'category', 'is_global']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Saludo inicial'}),
            'shortcut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: /saludo'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Hola, gracias por contactarnos...'}),
            'channel': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ventas, Soporte'}),
            'is_global': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ConversationReportForm(forms.Form):
    client = forms.ModelChoiceField(
        queryset=Client.objects.all().order_by('name'),
        label="Cliente",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        label="Fecha Desde",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label="Fecha Hasta",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

class EmailAccountAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        label="Contraseña"
    )

    class Meta:
        model = EmailAccount
        fields = "__all__" 
        exclude = ("encrypted_password",)

    def save(self, commit=True):
        instance = super().save(commit=False)

        password = self.cleaned_data.get("password")
        if password:
            instance.set_password(password)

        if commit:
            instance.save()

        return instance
