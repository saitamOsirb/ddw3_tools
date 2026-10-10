# ddw3_tools

Herramientas Python para preparar recursos de Digimon World 3 / Digimon World 2003 para motores actuales. **Primera entrega: extracción de videos desde imágenes de disco PS1 y conversión a OGV (Godot 4).**

## Requisitos (Windows)

- Python 3.11+
- [jPSXdec](https://github.com/m35/jpsxdec) (descarga su distribución con ejecutable Java `jpsxdec.jar`, más Java)
- [FFmpeg](https://ffmpeg.org/download.html) instalado y en `PATH`

> Solo usa imágenes de discos que poseas legalmente. Los videos extraídos no deben subirse a este repositorio público.

## Instalación

```powershell
git clone https://github.com/saitamOsirb/ddw3_tools.git
cd ddw3_tools
py -m pip install -e .
py -m ddw3_tools --help
```

## Extracción de video desde BIN / ISO

**Paso 1: indexar la imagen PS1 con jPSXdec**

```powershell
py -m ddw3_tools index --disc "D:\Juegos\Digimon World 3.bin" --jpsxdec "D:\Herramientas\jPSXdec\jpsxdec.jar" --output "D:\Extraccion\disco.idx"
```

**Paso 2: listar las secuencias** (IDs del índice para identificar intro)

```powershell
py -m ddw3_tools list --index "D:\Extraccion\disco.idx" --jpsxdec "D:\Herramientas\jPSXdec\jpsxdec.jar"
```

**Paso 3: extraer una secuencia de video**

```powershell
py -m ddw3_tools extract --index "D:\Extraccion\disco.idx" --jpsxdec "D:\Herramientas\jPSXdec\jpsxdec.jar" --item "ID_DEL_VIDEO" --output "D:\Extraccion\videos"
```

jPSXdec puede producir AVI y WAV u otros formatos; identifica los archivos efectivamente exportados antes de convertir. Para clips que requieran parámetros especiales, usa `--extra` para pasar opciones adicionales a jPSXdec, o consulta la ayuda del ejecutable.

**Paso 4: convertir a video OGV compatible con Godot**

```powershell
py -m ddw3_tools convert --input "D:\Extraccion\videos\intro.avi" --output "D:\developer\godot-digimon-world-3\client\src\assets\intro\intro.ogv"
```

Puedes convertir todos los archivos AVI/MP4/MKV de una carpeta:

```powershell
py -m ddw3_tools convert-dir --input "D:\Extraccion\videos" --output "D:\Extraccion\ogv"
```

Los comandos `index`, `list`, `extract` son adaptadores del CLI jPSXdec; no implementan un decodificador STR propio. La herramienta **no supone que cualquier ISO contenga videos identificables**: si jPSXdec no encuentra secuencias, consulta su salida y prueba una imagen BIN de sectores PS1 completos (2352 bytes), no una ISO reducida a 2048 bytes/sector.

Consulta `py -m ddw3_tools <comando> --help` para opciones. El proyecto no contiene ROMs ni recursos originales.

## Descargar assets de mapas desde ddw3

El repositorio [ddw3](https://github.com/saitamOsirb/ddw3) contiene recursos de mapas de **Digimon World 2003**, entre ellos:
- `map-tile/dw2003/z_stage/<stage>/*.toml`: definición de capas, offsets y recortes.
- `tim/dw2003/z_stage/<stage>/*.png`: texturas PNG extraídas.
- `tim/dw2003/z_stage/<stage>/*.toml`: metadatos de texturas.
- `*.clut.png`: paletas de color cuando existen.

Primero, listar un stage sin descargar:

```powershell
py -m ddw3_tools maps-download --stage s200pack --output "D:\\developer\\ddw3_maps" --list-only
```

Descargar el stage seleccionado:

```powershell
py -m ddw3_tools maps-download --stage s200pack --output "D:\\developer\\ddw3_maps"
```

Descargar todos los stages publicados en esas carpetas:

```powershell
py -m ddw3_tools maps-download --output "D:\\developer\\ddw3_maps"
```

El comando preserva las rutas del repositorio y omite archivos ya descargados. Utiliza la API pública de GitHub, por lo que puede alcanzar límites de solicitudes en descargas grandes. **No reconstruye todavía los mapas jugables de Godot**: descarga las texturas y los manifiestos necesarios para el próximo paso de composición de capas y atlas. Tampoco descarga la ISO original.

## Alcance siguiente

- Identificación y conversión de sprites TIM y paletas.
- Extracción de MAP y composición de capas/tiles.
- Manifiestos para Godot (PNG/atlas/navegación).
