import csv
import filecmp
import math
import os
import shutil
import statistics
import struct
import subprocess
import sys
import time
from contextlib import ExitStack
from shannon import ENTRY_FORMAT, HEADER_FORMAT, MAGIC

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FILES = [
  os.path.join(BASE_DIR, "tests", name)
  for name in (
    "prueba_1_pequena.txt",
    "prueba_2_texto_natural.txt",
    "prueba_3_alta_repeticion.txt",
    "prueba_4_baja_repeticion.txt",
  )
]
RESULTS_DIR = os.path.join(BASE_DIR, "results")
TEMP_DIR = os.path.join(BASE_DIR, "temp_benchmark")
REPEAT_COUNT = 3
SMALL_FILE_LIMIT = 1024
ALGORITHMS = (
  "Shannon O(2) (Propio)",
  "7-Zip LZMA2 (Externo)",
  "gzip -6 (Baseline)",
)

def _build_algorithms():
  python = sys.executable
  return [
    {
      "name": ALGORITHMS[0],
      "suffix": ".tdi",
      "compress": {
        "command": [python, os.path.join(BASE_DIR, "compressor.py"), "{input}", "{output}"],
      },
      "decompress": {
        "command": [python, os.path.join(BASE_DIR, "decompressor.py"), "{input}", "{output}", "-q"],
      },
      "header_size": _tdi_header_size,
    },
    {
      "name": ALGORITHMS[1],
      "suffix": ".7z",
      "compress": {
        "command": ["7z", "a", "-t7z", "-m0=LZMA2", "-mx=5", "-bd", "-y", "{output}", "{input}"],
      },
      "decompress": {
        "command": ["7z", "x", "-so", "-bd", "{input}"],
        "stdout_to_output": True,
      },
      "header_size": None,
    },
    {
      "name": ALGORITHMS[2],
      "suffix": ".gz",
      "compress": {
        "command": ["gzip", "-n", "-6", "-c"],
        "stdin_from_input": True,
        "stdout_to_output": True,
      },
      "decompress": {
        "command": ["gzip", "-d", "-c", "{input}"],
        "stdout_to_output": True,
      },
      "header_size": None,
    },
  ]


def _execute_command(action, input_path, output_path):
  command = [
    part.format(input=input_path, output=output_path)
    for part in action["command"]
  ]

  with ExitStack() as stack:
    stdin = None
    if action.get("stdin_from_input"):
      stdin = stack.enter_context(open(input_path, "rb"))

    if action.get("stdout_to_output"):
      stdout = stack.enter_context(open(output_path, "wb"))
    else:
      stdout = subprocess.PIPE

    result = subprocess.run(
      command,
      stdin=stdin,
      stdout=stdout,
      stderr=subprocess.PIPE,
      text=True,
    )

  if result.returncode != 0:
    details = result.stderr or result.stdout or "sin detalle del proceso"
    raise RuntimeError(f"Comando fallido ({result.returncode}): {details.strip()}")


def _take_measurement(action, input_path, output_path):
  samples = []
  for _ in range(REPEAT_COUNT):
    if os.path.exists(output_path):
      os.remove(output_path)
    start = time.perf_counter()
    _execute_command(action, input_path, output_path)
    samples.append((time.perf_counter() - start) * 1000)
    if not os.path.isfile(output_path):
      raise RuntimeError(f"El comando no generó la salida esperada: {output_path}")
  return samples


def calculate_weissman(r_global, r_ref, t_global, t_ref, alpha=1.0):
  """W = alpha . (r_global / r_ref) . [ log(t_ref) / log(t_global)]
  \nW: Weissman Score de la solución evaluada.
  \nalpha: Constante de escala. Para el práctico: alpha = 1.
  \nr_global: Ratio de compresión de la solución evaluada.
  \nr_ref: Ratio de gzip-6 sobre exactamente el mismo corpus.
  \nt_global: Tiempo de compresión de la solución evaluada.
  \nt_ref: Tiempo de compresión de gzip-6 en el mismo entorno
  """
  if r_global <= 0 or r_ref <= 0 or t_global <= 0 or t_ref <= 0:
    raise ValueError("Ratio y tiempos deben ser positivos para Weissman.")
  if math.isclose(t_global, 1.0) or math.isclose(t_ref, 1.0):
    return None
  return alpha * (r_global / r_ref) * (math.log(t_ref) / math.log(t_global))


def _tdi_header_size(archive_path):
    header_size = struct.calcsize(HEADER_FORMAT)
    with open(archive_path, "rb") as archive:
        archive.seek(len(MAGIC))          # saltear el magic
        header = archive.read(header_size)

    if len(header) < header_size:
        raise ValueError("Archivo truncado: cabecera incompleta")

    fields = struct.unpack(HEADER_FORMAT, header)
    return len(MAGIC) + header_size + fields[3] * struct.calcsize(ENTRY_FORMAT)

def _make_row(file_name, algorithm, input_path, archive_path, compress_samples, decompress_samples, header_size=None):
  original_size = os.path.getsize(input_path)
  compressed_size = os.path.getsize(archive_path)
  compression_ms = statistics.median(compress_samples)
  decompression_ms = statistics.median(decompress_samples)
  ratio = original_size / compressed_size if compressed_size else 0
  saving_pct = (1 - compressed_size / original_size) * 100 if original_size else None
  relative_size_pct = compressed_size / original_size * 100 if original_size else None
  return {
    "Archivo": file_name,
    "Algoritmo": algorithm,
    "Tam_Original_bytes": original_size,
    "Tam_Comprimido_bytes": compressed_size,
    "Ratio": round(ratio, 6),
    "Ahorro_pct": round(saving_pct, 4) if saving_pct is not None else "N/A",
    "Tam_Relativo_pct": round(relative_size_pct, 4) if relative_size_pct is not None else "N/A",
    "Tiempo_Compresion_ms": round(compression_ms, 4),
    "Throughput_Compresion_MB_s": round(
      original_size / 1_000_000 / (compression_ms / 1000), 6
    ),
    "Tiempo_Descompresion_ms": round(decompression_ms, 4),
    "Throughput_Descompresion_MB_s": round(
      original_size / 1_000_000 / (decompression_ms / 1000), 6
    ),
    "Cabecera_bytes": header_size if header_size is not None else "N/A",
    "Overhead_Cabecera_pct": (
      round(header_size / compressed_size * 100, 4)
      if header_size is not None and compressed_size
      else "N/A"
    ),
    "Weissman_Global": "N/A",
  }


def run_benchmark():
  algorithms = _build_algorithms()
  rows = []
  original_sizes = {}
  files = []
  compressed_sizes = {algorithm: {} for algorithm in ALGORITHMS}
  compression_samples = {algorithm: {} for algorithm in ALGORITHMS}

  for input_path in TEST_FILES:
    if not os.path.isfile(input_path):
      print(f"Saltando '{input_path}': archivo no encontrado.")
      continue

    file_name = os.path.basename(input_path)
    file_size = os.path.getsize(input_path)
    original_sizes[file_name] = file_size

    # solo contamos los archivos mayor a un determinado tamaño
    # para calcular el weissman score: 
    if file_size > SMALL_FILE_LIMIT: files.append(file_name)

    for algorithm in algorithms:
      name = algorithm["name"]
      archive_path = os.path.join(TEMP_DIR, file_name + algorithm["suffix"])
      decoded_path = os.path.join(TEMP_DIR, file_name + algorithm["suffix"] + ".out")
      compress_samples = _take_measurement(
        algorithm["compress"], input_path, archive_path
      )
      decompress_samples = _take_measurement(
        algorithm["decompress"], archive_path, decoded_path
      )

      if not filecmp.cmp(input_path, decoded_path, shallow=False):
        raise ValueError(f"{name} no reconstruyó exactamente {file_name}.")
      
      compression_samples[name][file_name] = compress_samples
      compressed_sizes[name][file_name] = os.path.getsize(archive_path)
      rows.append(
        _make_row(
          file_name,
          name,
          input_path,
          archive_path,
          compress_samples,
          decompress_samples,
          algorithm["header_size"](archive_path) if algorithm["header_size"] else None,
        )
      )
    print(f"Mediciones completadas: {file_name} ({original_sizes[file_name]:,} bytes)")

  if files:
    total_original = sum(original_sizes[name] for name in files)
    global_ratios = { # Rglobal
      algorithm: total_original / sum(compressed_sizes[algorithm][name] for name in files) for algorithm in ALGORITHMS
    }
    global_times = { # Tglobal
      algorithm: statistics.median(
        sum(compression_samples[algorithm][name][repeat] for name in files) for repeat in range(REPEAT_COUNT)
      )
      for algorithm in ALGORITHMS
    }
    # ALGORITHMS[2] es gzip.
    reference_ratio = global_ratios[ALGORITHMS[2]] # Rref
    reference_time = global_times[ALGORITHMS[2]]   # Tref
    scores = {ALGORITHMS[2]: 1.0} # baseline
    for algorithm in ALGORITHMS[:2]:
      scores[algorithm] = calculate_weissman(
        global_ratios[algorithm],
        reference_ratio,
        global_times[algorithm],
        reference_time,
      )
    for row in rows:
      # agregamos el weissman score a todos los algoritmos.
      # como estamos calculando el global, este se va a repetir,
      # pero es la unica forma de guardarlo en el mismo archivo ...
      score = scores[row["Algoritmo"]]
      row["Weissman_Global"] = round(score, 6) if score is not None else "N/A"

  csv_path = os.path.join(RESULTS_DIR, "benchmark_results.csv")
  if rows:
    # finalmente escribimos el archivo .csv con todos los datos...
    with open(csv_path, "w", newline="", encoding="utf-8") as result_file:
      writer = csv.DictWriter(result_file, fieldnames=rows[0].keys())
      writer.writeheader()
      writer.writerows(rows)
  
  print(f"Resultados por archivo: {csv_path}")

if __name__ == "__main__":
  try:
    for req in ("7z", "gzip"):
      if not shutil.which(req):
        sys.exit(f"Falta {req} en PATH.")
    run_benchmark()
  except (OSError, ValueError, RuntimeError, struct.error) as error:
    print(f"Error en benchmark: {error}", file=sys.stderr)
    sys.exit(1)