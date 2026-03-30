# Plan de Implementación: Token Permanente para Make.com

## Objetivo
Eliminar la necesidad de reconectar Make.com cada 60 días mediante un System User de Meta con token que nunca expira.

## Problema actual
Make.com usa la sesión personal de Facebook (Ro Robert), cuyo token OAuth expira ~cada 60 días.
Cuando expira, Make.com pausa el escenario automáticamente y las publicaciones se detienen.

## Solución: System User de Meta Business

### Paso 1: Verificar el negocio en Meta Business Suite
1. Ir a **business.facebook.com** → Configuración del negocio → "Información del negocio"
2. Buscar la sección **"Verificación del negocio"**
3. Subir documentos (RUC de MEGAGYM o documento legal del negocio)
4. Esperar aprobación: **1 a 5 días hábiles**
5. Una vez verificado, se habilita la sección "Usuarios del sistema"

### Paso 2: Crear el System User
1. Business Suite → Configuración → Usuarios → **Usuarios del sistema** → "+ Agregar"
2. Nombre: `megagym-automacion`
3. Rol: **Administrador**

### Paso 3: Darle acceso a las páginas
1. En el System User → "Agregar activos"
2. **Páginas** → seleccionar página MEGAGYM → permiso: Administrador
3. **Cuentas de Instagram** → seleccionar cuenta MEGAGYM → permiso: Administrador

### Paso 4: Generar token permanente
1. En el System User → botón **"Generar token"**
2. Seleccionar la app de Make.com
3. Permisos necesarios:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_manage_posts`
   - `pages_read_engagement`
4. **Sin fecha de expiración**
5. Copiar el token (solo se muestra una vez)

### Paso 5: Configurar en Make.com
1. Ir a Make.com → Credentials → Connections
2. En "Conexión MEGAGYM" → editar → usar el nuevo token del System User
3. Verificar que el escenario sigue en **Active**
4. Probar con **"Run once"**

## Resultado esperado
- Token nunca expira
- Make.com nunca pausa el escenario por error de autenticación
- 0 intervención manual requerida

## Estado actual
- [ ] Pendiente de iniciar
- Bloqueado por: verificación del negocio en Meta (requiere RUC/doc legal)

---
*Creado: 30 de marzo de 2026*
