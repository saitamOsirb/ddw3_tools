# Guía de inspección y extracción de una ISO de Digimon World 3 / 2003

Esta guía describe **lo que realmente admite `ddw3_tools`** y cómo organizar una extracción local para su uso en Godot. No incluye imágenes comerciales del juego.

## 1. Preparación en Windows

Instala Python 3.11 o posterior, Java (para `jpsxdec.jar`), [jPSXdec](https://github.com/m35/jpsxdec) y [FFmpeg](https://ffmpeg.org/download.html). Comprueba los programas en PowerShell:

```powershell
py --version
java -version
ffmpeg -version
git clone https://github.com/saitamOsirb/ddw3_tools.git
cd ddw3_tools
py -m pip install -e .
py -m ddw3_tools --help
```

El paquete también instala el ejecutable `ddw3`, pero los ejemplos usan `py -m ddw3_tools`.

## 2. Estructura local recomendada

Mantén la imagen original fuera del repositorio (no la publiques). Ejemplo de carpetas:

```text
D:\DigimonExtract\
  original\Digimon World 3.bin
  tools\jPSXdec\jpsxdec.jar
  indices\
  videos\
  ogv\
  maps\
```

Si dispones de archivos `.cue` y `.bin`, conserva ambos. Para el análisis de sectores PS1 suele ser preferible un BIN de sectores completos (2352 bytes/sector) frente a una ISO de 2048 bytes/sector. El comando `index` acepta la ruta de imagen compatible que pueda leer jPSXdec.

## 3. Indexar la imagen y revisar el contenido detectado

```powershell
py -m ddw3_tools index --disc "D:\DigimonExtract\original\Digimon World 3.bin" --jpsxdec "D:\DigimonExtract\tools\jPSXdec\jpsxdec.jar" --output "D:\DigimonExtract\indices\disco.idx"
py -m ddw3_tools list --index "D:\DigimonExtract\indices\disco.idx" --jpsxdec "D:\DigimonExtract\tools\jPSXdec\jpsxdec.jar"
```

`index` invoca jPSXdec para generar el índice. `list` **lee e imprime el índice de texto**: no implementa un explorador completo del sistema de archivos ISO. Observa los identificadores de los elementos detectados antes de extraer.

## 4. Extraer un video por identificador

Sustituye `ID_DEL_VIDEO` por el identificador real mostrado en el índice:

```powershell
py -m ddw3_tools extract --index "D:\DigimonExtract\indices\disco.idx" --jpsxdec "D:\DigimonExtract\tools\jPSXdec\jpsxdec.jar" --item "ID_DEL_VIDEO" --output "D:\DigimonExtract\videos"
```

El adaptador solicita calidad alta y salida AVI RGB. Revisa los archivos creados en `videos`: el nombre real depende del material extraído. No hay opción `--extra` en el CLI actual.

## 5. Convertir video a OGV para Godot

```powershell
py -m ddw3_tools convert --input "D:\DigimonExtract\videos\intro.avi" --output "D:\DigimonExtract\ogv\intro.ogv"
py -m ddw3_tools convert-dir --input "D:\DigimonExtract\videos" --output "D:\DigimonExtract\ogv"
```

`convert-dir` procesa únicamente videos de la carpeta indicada (no recorre subdirectorios). Reconoce AVI, MP4, MKV, MOV, WEBM, MPG y MPEG. Usa `--overwrite` si necesitas reemplazar un OGV existente. La conversión usa video Theora y audio Vorbis; si una fuente no tiene audio, FFmpeg lo omite.

## 6. Conseguir texturas y metadatos de mapas ya extraídos

`maps-download` **no lee la imagen de disco**. Descarga los PNG y TOML públicos del repositorio [ddw3](https://github.com/saitamOsirb/ddw3).

```powershell
py -m ddw3_tools maps-download --stage s200pack --output "D:\DigimonExtract\maps" --list-only
py -m ddw3_tools maps-download --stage s200pack --output "D:\DigimonExtract\maps"
py -m ddw3_tools maps-download --output "D:\DigimonExtract\maps"
```

Las rutas se conservan bajo `map-tile/dw2003/z_stage/<stage>/` y `tim/dw2003/z_stage/<stage>/`. Puede haber límites de solicitudes de GitHub. Los archivos existentes se omiten; `--max-files` permite limitar la cantidad.

## 7. Clasificación de recursos y límites

| Recurso | Estado actual | Procedimiento |
| --- | --- | --- |
| Video detectado por jPSXdec | Compatible mediante herramienta externa | `index`, `list`, `extract` |
| Video OGV para Godot | Compatible | `convert`, `convert-dir` |
| PNG/TOML de mapas publicados en ddw3 | Descarga disponible | `maps-download` |
| Inspección general de directorios de la ISO | No implementado | Usar un explorador de imágenes de disco por separado |
| Extracción directa de sprites TIM desde ISO | No implementado | Desarrollo pendiente |
| Reconstrucción de mapas jugables / atlas Godot | No implementado | Desarrollo pendiente |
| Exportación de audio, modelos o scripts de juego | No implementado | Desarrollo pendiente |

## 8. Resolución de problemas

- **No encuentra Java/jPSXdec**: comprueba `java -version` y la ruta a `jpsxdec.jar`.
- **No encuentra FFmpeg**: agrega `ffmpeg` al `PATH` y abre una terminal nueva.
- **El índice está vacío o no detecta videos**: comprueba la región/versión del disco y prueba la imagen BIN completa; no está garantizado que toda imagen contenga videos reconocibles.
- **El índice ya existe**: usa otro nombre o aparta el anterior; `index` no lo sobrescribe.
- **El OGV ya existe**: añade `--overwrite`.
- **Fallan las descargas de mapas**: revisa acceso a GitHub, nombre del stage y límites de API.

## 9. Comprobaciones

```powershell
py -m ddw3_tools --help
py -m pip install pytest
py -m pytest
```

No publiques BIN, ISO, CUE ni recursos comerciales extraídos sin autorización.
