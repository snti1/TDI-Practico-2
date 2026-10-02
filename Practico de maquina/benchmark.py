import csv
import filecmp
import hashlib
import gzip
import json
import math
import os
import platform
import shutil
import statistics
import struct
import subprocess
import sys
import time
import zlib
from compressor import ENTRY_FORMAT, HEADER_FORMAT, compress
from decompressor import decompress


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


def ensure_directories():
  os.makedirs(RESULTS_DIR, exist_ok=True)
  os.makedirs(TEMP_DIR, exist_ok=True)


def _measure_repeated(operation):
  samples = []
  for _ in range(REPEAT_COUNT):
    start = time.perf_counter()
    operation()
    samples.append((time.perf_counter() - start) * 1000)
  return samples


def _gzip_compress(input_path, output_path):
  with open(input_path, "rb") as input_file, open(output_path, "wb") as raw_output:
    with gzip.GzipFile(
      filename="",
      mode="wb",
      fileobj=raw_output,
      compresslevel=6,
      mtime=0,
    ) as gzip_output:
      shutil.copyfileobj(input_file, gzip_output)


def _get_7zip():
  bundled = os.path.join(BASE_DIR, "7z.exe")
  executable = bundled if os.path.isfile(bundled) else shutil.which("7z")
  if not executable:
    executable = shutil.which("7za")
  if not executable:
    raise FileNotFoundError("No se encontró 7-Zip (7z.exe, 7z o 7za).")
  return executable


def _run_7zip(arguments):
  result = subprocess.run(arguments, capture_output=True, text=True)
  if result.returncode != 0:
    raise RuntimeError(f"Falló 7-Zip: {result.stderr or result.stdout}")


def measure_shannon_o2(input_path):
  output_path = os.path.join(
    TEMP_DIR, os.path.basename(input_path) + ".shannon.tdi"
  )
  samples = _measure_repeated(
    lambda: compress(input_path, output_path, verbose=False)
  )
  return output_path, samples


def measure_7zip(input_path):
  output_path = os.path.join(TEMP_DIR, os.path.basename(input_path) + ".7z")
  executable = _get_7zip()

  def operation():
    if os.path.exists(output_path):
      os.remove(output_path)
    _run_7zip(
      [
        executable,
        "a",
        "-t7z",
        "-m0=LZMA2",
        "-mx=5",
        "-bd",
        "-y",
        output_path,
        input_path,
      ]
    )

  samples = _measure_repeated(operation)
  return output_path, samples


def measure_gzip6(input_path):
  output_path = os.path.join(TEMP_DIR, os.path.basename(input_path) + ".gz")
  samples = _measure_repeated(lambda: _gzip_compress(input_path, output_path))
  return output_path, samples


def measure_shannon_decompression(archive_path, output_path):
  samples = _measure_repeated(
    lambda: decompress(archive_path, output_path, verbose=False)
  )
  return samples


def measure_gzip_decompression(archive_path, output_path):
  def operation():
    with gzip.open(archive_path, "rb") as gzip_input, open(
      output_path, "wb"
    ) as output_file:
      shutil.copyfileobj(gzip_input, output_file)

  return _measure_repeated(operation)


def measure_7zip_decompression(archive_path, output_path):
  executable = _get_7zip()

  def operation():
    with open(output_path, "wb") as output_file:
      result = subprocess.run(
        [executable, "x", "-so", "-bd", archive_path],
        stdout=output_file,
        stderr=subprocess.PIPE,
        text=False,
      )
    if result.returncode != 0:
      raise RuntimeError(f"Falló la extracción 7-Zip: {result.stderr!r}")

  return _measure_repeated(operation)


def calculate_weissman(r_sol, r_ref, t_sol_ms, t_ref_ms, alpha=1.0):
  if r_sol <= 0 or r_ref <= 0 or t_sol_ms <= 0 or t_ref_ms <= 0:
    raise ValueError("Ratio y tiempos deben ser positivos para Weissman.")
  if math.isclose(t_sol_ms, 1.0) or math.isclose(t_ref_ms, 1.0):
    return None
  return alpha * (r_sol / r_ref) * (math.log(t_ref_ms) / math.log(t_sol_ms))


def _tdi_header_size(archive_path):
  header_size = struct.calcsize(HEADER_FORMAT)
  with open(archive_path, "rb") as archive:
    if archive.read(4) != b"TDI2":
      raise ValueError("El compresor propio no generó un archivo TDI2.")
    header = archive.read(header_size)
  fields = struct.unpack(HEADER_FORMAT, header)
  return 4 + header_size + fields[3] * struct.calcsize(ENTRY_FORMAT)


def _make_row(file_name, algorithm, input_path, archive_path, compress_samples,
        decompress_samples, header_size=None):
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
  ensure_directories()
  seven_zip = _get_7zip()
  rows = []
  original_sizes = {}
  compressed_sizes = {algorithm: {} for algorithm in ALGORITHMS}
  compression_samples = {algorithm: {} for algorithm in ALGORITHMS}

  for input_path in TEST_FILES:
    if not os.path.isfile(input_path):
      print(f"Saltando '{input_path}': archivo no encontrado.")
      continue

    file_name = os.path.basename(input_path)
    original_sizes[file_name] = os.path.getsize(input_path)
    decoded_paths = {
      algorithm: os.path.join(TEMP_DIR, file_name + "." + suffix + ".out")
      for algorithm, suffix in (
        (ALGORITHMS[0], "shannon"),
        (ALGORITHMS[1], "7z"),
        (ALGORITHMS[2], "gzip"),
      )
    }

    shannon_path, shannon_times = measure_shannon_o2(input_path)
    seven_zip_path, seven_zip_times = measure_7zip(input_path)
    gzip_path, gzip_times = measure_gzip6(input_path)

    shannon_decode_times = measure_shannon_decompression(
      shannon_path, decoded_paths[ALGORITHMS[0]]
    )
    seven_zip_decode_times = measure_7zip_decompression(
      seven_zip_path, decoded_paths[ALGORITHMS[1]]
    )
    gzip_decode_times = measure_gzip_decompression(
      gzip_path, decoded_paths[ALGORITHMS[2]]
    )

    archive_paths = {
      ALGORITHMS[0]: shannon_path,
      ALGORITHMS[1]: seven_zip_path,
      ALGORITHMS[2]: gzip_path,
    }
    sample_sets = {
      ALGORITHMS[0]: (shannon_times, shannon_decode_times),
      ALGORITHMS[1]: (seven_zip_times, seven_zip_decode_times),
      ALGORITHMS[2]: (gzip_times, gzip_decode_times),
    }

    for algorithm in ALGORITHMS:
      if not filecmp.cmp(
        input_path, decoded_paths[algorithm], shallow=False
      ):
        raise ValueError(
          f"{algorithm} no reconstruyó exactamente {file_name}."
        )
      archive_path = archive_paths[algorithm]
      compress_samples, decompress_samples = sample_sets[algorithm]
      compression_samples[algorithm][file_name] = compress_samples
      compressed_sizes[algorithm][file_name] = os.path.getsize(archive_path)
      rows.append(
        _make_row(
          file_name,
          algorithm,
          input_path,
          archive_path,
          compress_samples,
          decompress_samples,
          _tdi_header_size(archive_path)
          if algorithm == ALGORITHMS[0]
          else None,
        )
      )

    print(f"Mediciones completadas: {file_name} ({original_sizes[file_name]:,} bytes)")

  performance_files = [
    name for name, size in original_sizes.items() if size >= SMALL_FILE_LIMIT
  ]
  global_summary = {}
  if performance_files:
    total_original = sum(original_sizes[name] for name in performance_files)
    global_ratios = {
      algorithm: total_original
      / sum(compressed_sizes[algorithm][name] for name in performance_files)
      for algorithm in ALGORITHMS
    }
    global_times = {
      algorithm: statistics.median(
        sum(
          compression_samples[algorithm][name][repeat]
          for name in performance_files
        )
        for repeat in range(REPEAT_COUNT)
      )
      for algorithm in ALGORITHMS
    }
    reference_ratio = global_ratios[ALGORITHMS[2]]
    reference_time = global_times[ALGORITHMS[2]]
    scores = {ALGORITHMS[2]: 1.0}
    for algorithm in ALGORITHMS[:2]:
      scores[algorithm] = calculate_weissman(
        global_ratios[algorithm],
        reference_ratio,
        global_times[algorithm],
        reference_time,
      )
    for row in rows:
      score = scores[row["Algoritmo"]]
      row["Weissman_Global"] = round(score, 6) if score is not None else "N/A"
    global_summary = {
      "archivos_incluidos": performance_files,
      "tamano_original_total_bytes": total_original,
      "ratio_global": global_ratios,
      "mediana_tiempo_total_compresion_ms": global_times,
      "weissman_global": scores,
    }

  csv_path = os.path.join(RESULTS_DIR, "benchmark_results.csv")
  if rows:
    with open(csv_path, "w", newline="", encoding="utf-8") as result_file:
      writer = csv.DictWriter(result_file, fieldnames=rows[0].keys())
      writer.writeheader()
      writer.writerows(rows)

  metadata = {
    "repeticiones": REPEAT_COUNT,
    "unidad_tiempo": "ms",
    "MB": "1,000,000 bytes",
    "exclusion_temporal_archivo_menor_a_bytes": SMALL_FILE_LIMIT,
    "baseline": "gzip -6, sin nombre ni timestamp (gzip Python, mtime=0)",
    "solucion_externa": "7-Zip 7z/LZMA2 -mx=5 (Normal)",
    "7zip_ejecutable": seven_zip,
    "python": sys.version,
    "plataforma": platform.platform(),
    "zlib": zlib.ZLIB_VERSION,
    "sha256_entradas": {
      os.path.basename(path): _sha256_file(path)
      for path in TEST_FILES
      if os.path.isfile(path)
    },
    "resumen_global": global_summary,
  }
  with open(os.path.join(RESULTS_DIR, "benchmark_summary.json"), "w", encoding="utf-8") as summary_file:
    json.dump(metadata, summary_file, indent=2, ensure_ascii=True)

  print(f"Resultados por archivo: {csv_path}")
  print("Weissman global (sin la prueba pequeña):")
  for algorithm, score in global_summary.get("weissman_global", {}).items():
    display = f"{score:.6f}" if score is not None else "N/A (log(1 ms))"
    print(f"  {algorithm}: {display}")


def _sha256_file(path):
  digest = hashlib.sha256()
  with open(path, "rb") as input_file:
    for chunk in iter(lambda: input_file.read(65536), b""):
      digest.update(chunk)
  return digest.hexdigest()


if __name__ == "__main__":
  try:
    run_benchmark()
  except (OSError, ValueError, RuntimeError, struct.error) as error:
    print(f"Error en benchmark: {error}", file=sys.stderr)
    sys.exit(1)