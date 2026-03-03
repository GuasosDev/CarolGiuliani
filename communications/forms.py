from django import forms
from .models import QuickReply

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
