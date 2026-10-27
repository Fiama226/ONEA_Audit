# Object storage (S3) - decision pending

The `minio` and `minio-init` services in `docker/compose.yml` sit under the compose
profile `storage` and are not started by default. `MINIO_IMAGE` and `MINIO_MC_IMAGE`
default to the invalid placeholder `minio-image-not-chosen:replace-me` so that no
unvetted image can be pulled by accident.

Why: upstream `minio/minio` and `minio/mc` are no longer published on Docker Hub or
quay.io, and community forks are not vetted.

Before lot 4 (documents), the project owner must choose a vetted, open-source,
S3-compatible store, for example MinIO built from source, Garage or SeaweedFS, then:

1. set `MINIO_IMAGE` (and `MINIO_MC_IMAGE` if an `mc` client is used) in `.env`;
2. adapt the healthcheck and `minio-init` bucket creation (`onea-documents`) if the
   chosen store is not MinIO;
3. run `make up WITH_STORAGE=1` and `bash scripts/check-services.sh --with-storage`.
