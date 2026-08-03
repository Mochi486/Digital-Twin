# 50 Mbps and 100 Mbps bandwidth evidence supplement

Status: `SUPPLEMENTARY_REPLICATION`.

The pre-dissertation audit found only historical single-value summaries (47.9 Mbps at 50 Mbps and 95.7 Mbps at 100 Mbps) in commit `11fc2c81f724ecfeb73085cb05f5ec5a63b9fe21`; it did not retain raw iperf3 output, per-run records, or a batch manifest. Consequently, these are not reported as `RECOVERED_ORIGINAL_EVIDENCE`.

The retained supplement uses the original direct two-node reverse TCP iperf3 methodology (five seconds, `my-iperf-tc`, server-side TBF) on the stated baseline commit. It is new evidence and does not alter formal results. The 50 Mbps cohort completed five successful runs. The primary 100 Mbps batch contains one preserved iperf3 failure; the explicit run-06 retry supplied the fifth valid measurement.

| configured bandwidth | valid / attempted | mean Mbps | SD Mbps | 95% CI half-width Mbps | min–max Mbps | mean/configured |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | 5 / 5 | 41.500 | 3.362 | 4.175 | 36.900–45.800 | 0.830 |
| 100 | 5 / 6 | 78.780 | 11.684 | 14.508 | 58.400–87.300 | 0.788 |

All successful and failed records appear in `runs/bandwidth-evidence-supplement/per-run-results.csv`, including ten preliminary Docker-permission failures and an additional 100 Mbps diagnostic attempt. They are retained for provenance but are not mixed into the planned cohort. Raw iperf3 output and command stdout/stderr are retained beneath the cited attempt directories.
