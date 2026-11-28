import os
import whitebox

DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_TEST_DIR = "sorties_whitebox_test"

outils_requis = [
    "FillDepressions",
    "BreachDepressions",
    "D8Pointer",
    "D8FlowAccumulation",
    "Watershed",
    "ExtractStreams",
]

wb = whitebox.WhiteboxTools()
wb.verbose = False

print("WhiteboxTools initialisé avec succès.")
print("Version :", wb.version())

disponibles = {}
for outil in outils_requis:
    try:
        aide = wb.tool_help(outil)
        ok = bool(aide and len(aide.strip()) > 0)
    except Exception:
        ok = False
    disponibles[outil] = ok
    print(f"  - {outil:20s} : {'DISPONIBLE' if ok else 'INDISPONIBLE'}")

if not all(disponibles.values()):
    raise RuntimeError("Un ou plusieurs outils hydrologiques requis sont indisponibles.")

if os.path.exists(DEM_PATH):
    os.makedirs(OUT_TEST_DIR, exist_ok=True)
    dem_abs = os.path.abspath(DEM_PATH)
    breached_abs = os.path.abspath(os.path.join(OUT_TEST_DIR, "test_breach.tif"))
    fdir_abs = os.path.abspath(os.path.join(OUT_TEST_DIR, "test_d8_pointer.tif"))
    facc_abs = os.path.abspath(os.path.join(OUT_TEST_DIR, "test_d8_acc.tif"))

    print("\nTest d'exécution sur :", DEM_PATH)
    status_breach = wb.breach_depressions(dem=dem_abs, output=breached_abs)
    status_fdir = wb.d8_pointer(dem=breached_abs, output=fdir_abs)
    status_facc = wb.d8_flow_accumulation(
        i=fdir_abs,
        out_type="cells",
        output=facc_abs,
    )

    print("  BreachDepressions    :", "OK" if status_breach == 0 else f"Code {status_breach}")
    print("  D8Pointer            :", "OK" if status_fdir == 0 else f"Code {status_fdir}")
    print("  D8FlowAccumulation   :", "OK" if status_facc == 0 else f"Code {status_facc}")
else:
    print(f"\nFichier '{DEM_PATH}' non trouvé dans le dossier courant ; vérification des outils uniquement.")