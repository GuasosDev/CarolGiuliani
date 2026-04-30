# Design System — GD-CarolGiuliani CRM Multicanal

## 1. Visión General del Producto

**GD-CarolGiuliani** es una plataforma de comunicación y gestión de clientes (CRM) multicanal diseñada para equipos de atención al cliente. Centraliza conversaciones de **WhatsApp Business** y **Correo Electrónico** en una única interfaz de escritorio tipo _chat inbox_, con soporte para múltiples agentes, asignaciones automáticas y supervisión en tiempo real.

### Tipo de Interfaz
- **Aplicación web de escritorio** (responsive secundario)
- **Paradigma**: Bandeja de entrada dividida en tres columnas (sidebar → lista de conversaciones → área de chat)
- **Actualización en tiempo real** vía WebSockets

---

## 2. Usuarios y Roles

| Rol | Descripción |
|-----|-------------|
| **Agente** | Atiende conversaciones asignadas. Ve solo sus chats. |
| **Supervisor** | Ve todos los agentes y conversaciones. Accede a métricas. |
| **Admin / Superusuario** | Control total: configuración de cuentas, usuarios y sistema. |

---

## 3. Mapa de Pantallas (Sitemap)

```
├── Login / Registro
├── Dashboard Principal (Bandeja de Conversaciones)
│   ├── Vista por Canal (WhatsApp / Email / Todos)
│   ├── Vista por Estado (Activo / Pendiente / Cerrado / No Leído)
│   └── Vista Inbox (agrupado por cliente)
├── Detalle de Conversación (Chat)
│   ├── Área de mensajes
│   ├── Panel de contacto (info del cliente)
│   └── Notas internas
├── Vista 360° del Contacto
├── Dashboard del Agente (mis métricas)
├── Dashboard del Supervisor (métricas globales + workload)
├── Respuestas Rápidas (CRUD)
├── Menús de Bienvenida (WhatsApp)
│   └── Configurar opciones y asignaciones
├── Configuración
│   ├── Cuentas WhatsApp
│   ├── Cuentas de Email (IMAP/SMTP)
│   ├── Usuarios y Roles
│   └── Áreas de Trabajo
└── Reportes (PDF por cliente y rango de fechas)
```

---

## 4. Paleta de Colores

### Tema Principal (Oscuro / Profesional)

| Token | Valor | Uso |
|-------|-------|-----|
| `--color-bg-deep` | `#0D1117` | Fondo de página / sidebar izquierdo |
| `--color-bg-surface` | `#161B22` | Fondo del panel de lista |
| `--color-bg-card` | `#21262D` | Tarjetas de conversación, inputs |
| `--color-bg-hover` | `#2D333B` | Hover sobre conversación / botón |
| `--color-border` | `#30363D` | Separadores sutiles |
| `--color-primary` | `#25D366` | WhatsApp verde (acciones principales, badges) |
| `--color-primary-dark` | `#1DA851` | Hover de botón primario |
| `--color-accent-email` | `#4A90E2` | Indicador de canal Email (azul) |
| `--color-accent-warning` | `#F39C12` | Conversaciones pendientes |
| `--color-accent-danger` | `#E74C3C` | Conversaciones urgentes / errores |
| `--color-accent-success` | `#2ECC71` | Confirmaciones, "enviado" |
| `--color-text-primary` | `#E6EDF3` | Texto principal |
| `--color-text-secondary` | `#8B949E` | Timestamps, meta-info |
| `--color-text-muted` | `#484F58` | Placeholders |

### Luz de estado de mensaje
| Estado | Color |
|--------|-------|
| Enviado | `#8B949E` |
| Entregado | `#4A90E2` |
| Leído | `#25D366` |
| Fallido | `#E74C3C` |

---

## 5. Tipografía

```
Font Principal: "Inter" (Google Fonts)
Fallback: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif

--font-size-xs:   11px  → timestamps, badges pequeños
--font-size-sm:   13px  → metadata, sidebar secundario
--font-size-base: 14px  → texto de conversaciones, inputs
--font-size-md:   15px  → nombre de contacto en lista
--font-size-lg:   18px  → títulos de sección
--font-size-xl:   22px  → métricas numéricas en dashboards

Font Weight:
  400 → texto corriente
  500 → nombres, etiquetas
  600 → botones, encabezados de sección
  700 → cifras métricas, énfasis
```

---

## 6. Layout de Tres Columnas (Pantalla Principal)

```
┌─────────────────────────────────────────────────────────────────┐
│ SIDEBAR NAV    │  LISTA CONVERSACIONES  │  ÁREA DE CHAT         │
│  (64px / icon) │      (320px)           │  (flex-grow)          │
│                │                        │                        │
│  🏠 Dashboard  │  [filtros rápidos]     │  ┌── header contacto ─┐│
│  👤 Clientes   │  ─────────────────     │  │ Nombre + canal     ││
│  💬 Chat       │  [Tarjeta conversac.]  │  │ Estado + asignado  ││
│  ⚙️ Settings   │  [Tarjeta conversac.]  │  └────────────────────┘│
│                │  [Tarjeta conversac.]  │                        │
│  ────────────  │                        │  [burbujas de chat]    │
│  Avatar user   │                        │                        │
│  Rol          │                        │  ┌── input area ───────┐│
└─────────────────────────────────────────────────────────────────┘
```

**Breakpoints responsive:**
- `≥ 1280px`: 3 columnas completas
- `≥ 768px`: sidebar colapsado (íconos) + lista + chat
- `< 768px`: vista móvil en tabs (lista → chat)

---

## 7. Componentes UI

### 7.1 Tarjeta de Conversación (Lista)
```
┌────────────────────────────────────────────────┐
│ [Avatar/Iniciales]  Nombre Cliente       [hora]│
│                     Canal 💬 / 📧              │
│                     Último mensaje preview...   │
│ [badge: Urgente]  [badge: sin leer x3]          │
└────────────────────────────────────────────────┘
```
- **Estado activo**: borde izquierdo de 3px en `--color-primary`
- **No leída**: fondo `--color-bg-hover`, punto verde animado
- **Asignada a otro**: opacidad reducida si es supervisor viendo

### 7.2 Burbuja de Mensaje

**Entrante (inbound):**
```
[Avatar]  ┌─────────────────────────────┐
          │  Texto del mensaje aquí     │  bg: --color-bg-card
          └─────────────────────────────┘
          10:35 am
```

**Saliente (outbound):**
```
                 ┌─────────────────────────────┐
                 │  Texto del mensaje aquí     │  bg: --color-primary con 15% opacity
                 └─────────────────────────────┘
                                10:36 am ✓✓
```

- Mensajes con archivos/media: preview de imagen o ícono de documento + nombre
- Notas internas: fondo amarillo `#3D3100`, ícono candado 🔒, texto en itálica

### 7.3 Panel de Contacto (Right Sidebar)

```
┌──────────────────────────────────┐
│ [Avatar grande]                  │
│ Nombre Completo                  │
│ 🏢 Razón Social                  │
│ 📞 +54 9 ...                     │
│ 📧 email@ejemplo.com             │
│ 🏷️ [tag1] [tag2]                │
├──────────────────────────────────┤
│ CANAL PREFERIDO: WhatsApp        │
│ ASIGNADO A: Agente X             │
│ PRIORIDAD: [selector]            │
├──────────────────────────────────┤
│ NOTAS INTERNAS                   │
│ [textarea + btn Agregar]         │
│ > Nota de Juan hace 2h           │
└──────────────────────────────────┘
```

### 7.4 Input de Mensaje

```
┌──────────────────────────────────────────────────┐
│ [📎 Adjunto]  [⚡ Respuesta Rápida]              │
├──────────────────────────────────────────────────┤
│  Escribí un mensaje...                           │
│                                              [→]  │
└──────────────────────────────────────────────────┘
```
- Para Email: se expande con campos Asunto, CC, BCC y editor rich text
- Respuestas Rápidas: popup al escribir `/` o al presionar el botón

### 7.5 Filtros de la Lista

```
[Todos] [WhatsApp] [Email]    ← tabs de canal
[Activo] [Pendiente] [Cerrado] [Sin leer]  ← pills de estado
[🔍 Buscar conversación...]
```

### 7.6 Badges y Pills

| Tipo | Estilo |
|------|--------|
| Canal WhatsApp | Verde, ícono WA |
| Canal Email | Azul, ícono ✉️ |
| Estado Activo | Verde outline |
| Estado Pendiente | Naranja outline |
| Estado Cerrado | Gris |
| Urgente | Rojo sólido |
| Unread count | Verde sólido, circular |

### 7.7 Menú de Bienvenida WhatsApp (Configuración)
- Lista de menús con toggle ON/OFF
- Formulario en línea para editar palabras clave disparadoras
- Tabla de opciones numeradas + usuario asignado por opción

---

## 8. Pantallas Clave

### 8.1 Dashboard Principal
- **Filtros superiores**: canal + estado + búsqueda
- **Lista central** con scroll infinito o paginación
- **Chat a la derecha** cargado dinámicamente (HTMX)
- **Contador de no leídos** en ícono del sidebar

### 8.2 Dashboard del Supervisor
```
┌──────────────────────────────────────────────────────┐
│  MÉTRICAS GLOBALES                                   │
│  [Total Convs]  [Abiertas]  [Cerradas Hoy]           │
├──────────────────────────────────────────────────────┤
│  DISTRIBUCIÓN DE CANALES      │  WORKLOAD AGENTES    │
│  [Donut: WA% / Email%]        │  [Tabla: agente/cant]│
├──────────────────────────────────────────────────────┤
│  FILTROS: [Agente▼] [Desde] [Hasta] [Canal▼]         │
└──────────────────────────────────────────────────────┘
```

### 8.3 Dashboard del Agente
```
┌────────────────────────────────────┐
│  Mis Conversaciones Activas: 12    │
│  Cerradas Hoy: 8                   │
├────────────────────────────────────┤
│  ACTIVIDAD RECIENTE                │
│  > Cliente A — hace 5min           │
│  > Cliente B — hace 22min          │
└────────────────────────────────────┘
```

### 8.4 Vista 360° del Contacto
```
┌────────────────────────────────────────────────┐
│  [Avatar]  Nombre Cliente                      │
│  Datos de contacto completos                   │
├────────────────────────────────────────────────┤
│  HISTORIAL DE CONVERSACIONES                   │
│  ─ [WhatsApp - Activo - hace 2 días]           │
│  ─ [Email - Cerrado - hace 1 semana]           │
├────────────────────────────────────────────────┤
│  MENSAJES RECIENTES (timeline cronológico)     │
└────────────────────────────────────────────────┘
```

### 8.5 Configuración (solo Admin/Supervisor)
- **Tabs**: Cuentas WA | Cuentas Email | Usuarios | Áreas | Roles | Respuestas Rápidas
- Formularios en acordeón o modal por elemento
- Toggle de activar/desactivar por cuenta

---

## 9. Microinteracciones y Animaciones

| Elemento | Animación |
|----------|-----------|
| Conversación seleccionada | Slide-in suave del panel de chat (200ms ease) |
| Nuevo mensaje entrante | Toast notification + sonido (opcional) |
| Envío de mensaje | Burbuja aparece con fade-in desde abajo |
| Badge de no leídos | Pulso suave (keyframe pulse 1.5s infinite) |
| Toggle ON/OFF | Transición de color suave 150ms |
| Hover en tarjeta | Elevación sutil (box-shadow leve) |
| Carga de conversación | Skeleton loader (3 líneas animadas) |
| Cambio de estado | Badge cambia con fade (100ms) |

---

## 10. Iconografía

- **Librería base**: Heroicons o Phosphor Icons (outline style)
- **WhatsApp**: Logo oficial SVG
- **Email**: ícono de sobre
- **Adjuntos**: paperclip
- **Notas internas**: candado / lock
- **Asignar**: user-plus
- **Transferir**: arrow-right-circle
- **Cerrar conversación**: check-circle
- **Urgente**: exclamation-triangle

---

## 11. Estados de UI

### Vacíos (Empty States)
- Lista sin conversaciones: ilustración de bandeja vacía + texto "No hay conversaciones"
- Chat sin abrir: ilustración de burbuja + "Seleccioná una conversación para comenzar"

### Carga
- Skeleton loaders para tarjetas de conversación
- Spinner circular en el área de chat al cambiar

### Error
- Toast de error rojo en esquina superior derecha, auto-dismiss 5s
- Mensaje inline en el chat si falla el envío

---

## 12. Flujos de Usuario Prioritarios

### Flujo 1: Agente atiende conversación entrante
1. Agente ve badge de no leído en sidebar
2. Click en conversación → chat se carga al lado
3. Lee mensajes → puede responder, marcar pendiente, agregar nota interna
4. Usa `/` para respuestas rápidas
5. Cierra conversación con botón "Resolver"

### Flujo 2: Supervisor asigna conversación
1. Supervisor ve conversación sin asignar
2. Click en "Asignar" → modal con lista de agentes
3. Elige agente → conversación se asigna y el agente la recibe en tiempo real

### Flujo 3: Configurar menú de bienvenida WhatsApp
1. Admin va a Configuración → Menús de Bienvenida
2. Crea nuevo menú → agrega texto de saludo
3. Agrega opciones (1. Ventas, 2. Soporte) → asigna usuario a cada opción
4. Activa el menú → guarda

### Flujo 4: Crear cliente desde conversación desconocida
1. Llega mensaje de número no registrado
2. Agente abre el chat → panel de contacto muestra "Desconocido"
3. Click "Crear Cliente" → modal con nombre, teléfono, email
4. Guarda → contacto queda vinculado a la conversación

---

## 13. Notas para Stitch

- **Framework**: Django + HTMX (las interacciones dinámicas son parciales HTML sin SPA)
- **No usar**: frameworks JS pesados; preferir interacciones declarativas
- **Foco en**: la pantalla principal (3 columnas) es la más crítica para UX
- **Accesibilidad**: mantener contraste WCAG AA mínimo
- **Idioma UI**: Español latinoamericano (Argentina)
- **Tiempo real**: mostrar indicadores de "escribiendo..." y actualizaciones de estado de mensaje (enviado/entregado/leído)
- **Mobile**: prioridad secundaria, pero la vista de lista de conversaciones debe ser funcional en tablet

---

_Generado para: GD-CarolGiuliani · GuasosDev · 2026_
