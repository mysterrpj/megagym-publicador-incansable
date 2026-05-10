# TODO

## Alta
- [x] Implementar soporte de videos programados desde `calendario_publicaciones.csv`.
- [x] Ajustar Make para publicar videos en Facebook e Instagram/Reel usando `asset_type = video`.
- [x] Validar prueba final de video con resultado `Success` en Make.
- [ ] Confirmar que el escenario de Make quede activo despues de los cambios.
- [ ] Probar una publicacion real futura de video desde GitHub Actions, no solo webhook manual.

## Media
- [ ] Documentar con capturas o pasos exactos la configuracion final de Make.
- [ ] Revisar que el importador de WhatsApp soporte videos de forma estable.
- [ ] Evaluar si conviene mover videos grandes fuera de GitHub si empiezan a crecer en peso.
- [ ] Actualizar nombres en calendario a una columna generica `archivo` en una migracion futura, manteniendo compatibilidad con `imagen_archivo`.

## Baja
- [ ] Revisar warning local de Git sobre `C:\Users\Lenovo\.config\git\ignore`.
- [ ] Considerar migrar de `google.generativeai` a `google.genai` por aviso de deprecacion en GitHub Actions.
