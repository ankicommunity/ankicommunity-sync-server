#!/usr/bin/env bash
# file: jupyter.sh
# description: Run Jupyter Notebooks.

[[ ! -z "${JUPYTER_CMD}" ]] || JUPYTER_CMD=lab
[[ ! -z "${JUPYTER_NOTEBOOK_DIR}" ]] || JUPYTER_NOTEBOOK_DIR=docs/src/notebooks
${JUPYTER} ${JUPYTER_CMD} --notebook-dir=${JUPYTER_NOTEBOOK_DIR}