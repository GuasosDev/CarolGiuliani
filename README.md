# 🚀 GD-CarolGiuliani: Sistema de Gestión y Comunicaciones Multicanal

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2%2B-092e20?style=for-the-badge&logo=django)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

Este repositorio contiene un sistema integral de gestión (CRM) y comunicaciones multicanal diseñado para centralizar la interacción con clientes a través de **WhatsApp Business** y **Correo Electrónico Corporativo**, integrado en una plataforma de gestión empresarial robusta.

---

## 🌟 Características Principales

### 📱 Comunicación Multicanal
*   **WhatsApp Business API**: Integración completa con Meta para enviar y recibir mensajes, incluyendo soporte multimedia (imágenes, documentos, audios).
*   **Gestión Multi-agente**: Permite que múltiples agentes trabajen de forma simultánea utilizando el mismo número de WhatsApp corporativo.
*   **Correo Centralizado**: Soporte para Gmail, Outlook e IMAP/SMTP con sincronización automática en segundo plano.
*   **Conversaciones Unificadas**: Historial combinado de WhatsApp y Email vinculado directamente a la ficha del cliente.
*   **Vista 360° del Contacto**: Cronología completa de todas las interacciones, notas internas y archivos adjuntos en un solo lugar.

### ⚙️ Gestión Inteligente
*   **Asignación Automática**: Sistema de balanceo de carga que distribuye conversaciones entre agentes disponibles.
*   **Respuestas Rápidas**: Biblioteca de plantillas predefinidas con soporte para variables dinámicas (e.g., `{{client_name}}`).
*   **Notas Internas**: Colaboración entre agentes mediante anotaciones privadas en las conversaciones.
*   **Dashboard de Supervisión**: Métricas de rendimiento, tiempos de respuesta y monitoreo de carga de trabajo en tiempo real.

### 🔒 Seguridad y Arquitectura
*   **Encriptación Fernet**: Las credenciales de correo electrónico se almacenan de forma segura utilizando encriptación simétrica.
*   **WebSockets (Django Channels)**: Actualizaciones instantáneas en la interfaz sin necesidad de recargar la página.
*   **Tareas en Segundo Plano (Celery)**: Procesamiento asíncrono para envío de correos, sincronización de bandejas y reintentos automáticos.

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
| :--- | :--- |
| **Backend** | Python 3.10+ / Django 5.2 |
| **API** | Django REST Framework (DRF) |
| **Real-time** | Django Channels (Daphne) |
| **Base de Datos** | PostgreSQL / SQLite (Dev) |
| **Task Queue** | Celery + Redis |
| **Frontend** | HTML5, CSS3, Bootstrap 5 (Crispy Forms) |
| **Seguridad** | Cryptography (Fernet) |

---

## 📁 Estructura del Proyecto

*   `core/`: Gestión de usuarios, roles, áreas de trabajo y configuración global del sistema.
*   `clients/`: Módulo de gestión de clientes y base de datos de contactos.
*   `communications/`: El núcleo multicanal (handlers de WhatsApp/Email, WebSockets y API).
*   `gd_soft_gty/`: Configuración principal del proyecto Django, settings y ASGI/WSGI.

---

## 🚀 Instalación y Configuración

### 1. Requisitos Previos
*   Python 3.10+
*   Redis (requerido para Channels y Celery)
*   Acceso a WhatsApp Business API (Meta)

### 2. Clonar y Preparar Entorno
```bash
git clone https://github.com/GuasosDev/GD-CarolGiuliani.git
cd GD-CarolGiuliani
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuración Inicial
1.  Crea las migraciones y aplica la base de datos:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```
2.  Genera la clave de encriptación para comunicaciones:
    ```bash
    # Se generará automáticamente en 'fernet.key' al iniciar si no existe
    # o puedes configurarla en settings.py
    ```
3.  Crea un superusuario:
    ```bash
    python manage.py createsuperuser
    ```

### 4. Ejecución del Sistema
Para que todas las funcionalidades (WebSockets y tareas) operen correctamente, debes iniciar:

*   **Servidor ASGI (Daphne):**
    ```bash
    daphne -b 0.0.0.0 -p 8000 gd_soft_gty.asgi:application
    ```
*   **Celery Worker:**
    ```bash
    celery -A gd_soft_gty worker -l info
    ```
*   **Celery Beat (Sync tareas):**
    ```bash
    celery -A gd_soft_gty beat -l info
    ```

---

## 📖 Documentación Adicional
Para más detalles sobre la implementación y guías específicas:
*   [Guía de Configuración](setup_guide.md): Pasos detallados para configurar WhatsApp y Email.
*   [Plan de Implementación](implementation_plan.md): Detalles técnicos sobre la arquitectura del sistema.

---

## ✉️ Soporte y Contacto
**Guasos Dev** - Desarrollado para Carol Giuliani.

---
Developed with ❤️ by [Guasos Dev](https://github.com/GuasosDev)
