# ddw3_tools

Herramientas Python para preparar recursos de Digimon World 3 / Digimon World 2003 para motores actuales. **Primera entrega: extracción de videos desde imágenes de disco PS1 y conversión a OGV (Godot 4).**

## Documentación de extracción de ISO

La guía completa, con organización de carpetas, comandos de PowerShell, diagnóstico de errores y alcance real de cada herramienta, está en **[docs/iso/README.md](docs/iso/README.md)**.

Comandos implementados: `index`, `list`, `extract`, `convert`, `convert-dir` y `maps-download`. La extracción directa de TIM y la composición de mapas jugables todavía están pendientes.

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

jPSXdec puede producir AVI y WAV u otros formatos; identifica los archivos efectivamente exportados antes de convertir. Para clips que requieran parámetros especiales, consulta la ayuda de jPSXdec y ejecútalo directamente: esta versión del CLI no expone una opción `--extra`.

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


## Extracción experimental de imágenes TIM (sprites y texturas)

La herramienta ahora puede escanear bytes de una imagen BIN/ISO buscando estructuras **TIM estándar de PlayStation 1** y exportar sus imágenes como PNG RGBA. No necesita jPSXdec ni FFmpeg para este comando:

```powershell
py -m ddw3_tools sprites-extract --disc "D:\\DigimonExtract\\original\\Digimon World 3.bin" --output "D:\\DigimonExtract\\sprites"
```

También admite `--max-images 10000` (límite de estructuras TIM). Crea archivos `tim_<offset>_pal_<n>.png` y `manifest.json` con offsets, dimensiones, profundidad de color, paletas y archivos generados. Soporta TIM de 4, 8, 16 y 24 bits; para 4/8 bits exporta las variantes CLUT. En paletas indexadas el color negro cero se trata como transparente; la interpretación de transparencia PS1/STP puede requerir ajustes manuales.

**Limitaciones:** es un escáner de TIM estándar, no un extractor completo de sprites animados. Puede detectar texturas, fondos e interfaces, no solo personajes; no recompone animaciones ni decodifica contenedores comprimidos o formatos propietarios. Procesa la imagen completa en memoria, por lo que requiere RAM suficiente. Los resultados dependen de la versión/región y organización de la imagen.

## Alcance siguiente

- Identificación de sprites TIM empaquetados/comprimidos y reconstrucción de animaciones.
- Extracción de MAP y composición de capas/tiles.
- Manifiestos para Godot (PNG/atlas/navegación).
