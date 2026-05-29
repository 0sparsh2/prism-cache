.PHONY: install test eval eval-live gateway gateway-prism gateway-full redis-up prod-redis \
	check-redis check-gateway check-vllm phase-f-up \
	demo-faq demo-faq-dry demo-rag demo-tier2 demo-production demo-production-live \
	demo-phase-f demo-phase-f-chat demo-proxy scenario-org run-all run-all-cold run-demos ensure-infra flush-redis

LOAD_ENV = set -a && . ./.env && set +a

install:
	python3.12 -m venv .venv
	.venv/bin/pip install -e ".[dev,gateway,redis]"

test:
	.venv/bin/python -m pytest -q

eval:
	.venv/bin/python -m eval.run_benchmarks

eval-live:
	$(LOAD_ENV) && .venv/bin/python -m eval.run_benchmarks --live

redis-up:
	docker compose up -d redis

prod-redis:
	docker compose -f docker-compose.prod.yml up -d

check-redis:
	@redis-cli -p 6379 ping >/dev/null 2>&1 || (echo "Redis not reachable on :6379 — run: make prod-redis" && exit 1)
	@echo "Redis OK"

check-gateway:
	@$(LOAD_ENV) && curl -sf -H "Authorization: Bearer $$LITELLM_MASTER_KEY" \
		"$${LITELLM_BASE_URL:-http://localhost:4000}/health/liveliness" >/dev/null \
		|| (echo "LiteLLM not reachable — run: make gateway (separate terminal)" && exit 1)
	@echo "LiteLLM gateway OK"

check-vllm:
	@$(LOAD_ENV) && curl -sf "$${VLLM_BASE_URL:-http://localhost:8000/v1}/models" >/dev/null \
		|| (echo "vLLM not reachable on :8000 — run: make phase-f-up (GPU + HF_TOKEN required)" && exit 1)
	@echo "vLLM OK"

phase-f-up:
	@test -n "$$HF_TOKEN" || (echo "Set HF_TOKEN in .env before phase-f-up" && exit 1)
	docker compose -f docker-compose.vllm-lmcache.yml up -d

ensure-infra: prod-redis
	@sleep 2
	@$(MAKE) check-redis

gateway:
	$(LOAD_ENV) && .venv/bin/litellm --config gateway/litellm.multi.yaml --port 4000

gateway-prism:
	PYTHONPATH=src:gateway $(LOAD_ENV) && .venv/bin/litellm --config gateway/litellm.prism.yaml --port 4000

gateway-full:
	PYTHONPATH=src:gateway $(LOAD_ENV) && .venv/bin/litellm --config gateway/litellm.full.yaml --port 4000

demo-proxy:
	.venv/bin/python examples/proxy_lane_demo.py

demo-faq:
	$(LOAD_ENV) && .venv/bin/python examples/faq_litellm_gemini.py

demo-faq-dry:
	.venv/bin/python examples/faq_litellm_gemini.py --dry-run

demo-rag:
	$(LOAD_ENV) && .venv/bin/python examples/rag_litellm_demo.py --no-llm

demo-tier2:
	.venv/bin/python examples/tier2_faq_demo.py

demo-production:
	$(LOAD_ENV) && .venv/bin/python examples/production_app.py --dry-run

demo-production-live:
	$(LOAD_ENV) && .venv/bin/python examples/production_app.py

demo-phase-f:
	.venv/bin/python examples/phase_f_rag_vllm.py

demo-phase-f-chat:
	$(LOAD_ENV) && .venv/bin/python examples/phase_f_vllm_chat.py --chat

scenario-org:
	.venv/bin/python examples/org_scenario_tier3.py --users 500 --vector-latency-ms 50

scenario-org-fast:
	.venv/bin/python examples/org_scenario_tier3.py --users 500 --vector-latency-ms 0

flush-redis:
	@redis-cli -p 6379 ping >/dev/null 2>&1 && redis-cli -p 6379 FLUSHDB && echo "Redis FLUSHDB OK" \
		|| echo "Redis not running — skip flush"

run-demos:
	@echo "=== proxy lane (offline) ==="
	.venv/bin/python examples/proxy_lane_demo.py
	@echo "\n=== tier2 (offline) ==="
	.venv/bin/python examples/tier2_faq_demo.py
	@echo "\n=== tier3 RAG (offline) ==="
	$(LOAD_ENV) && .venv/bin/python examples/rag_litellm_demo.py --no-llm
	@echo "\n=== org scenario (fast) ==="
	.venv/bin/python examples/org_scenario_tier3.py --vector-latency-ms 0
	@echo "\n=== phase F scaffold ==="
	.venv/bin/python examples/phase_f_rag_vllm.py
	@echo "\n=== phase F vLLM probe ==="
	$(LOAD_ENV) && .venv/bin/python examples/phase_f_vllm_chat.py
	@if $(MAKE) -s check-redis 2>/dev/null; then \
		echo "\n=== production (live, Redis) ==="; \
		$(LOAD_ENV) && .venv/bin/python examples/production_app.py; \
	else \
		echo "\n=== production (dry-run, no Redis) ==="; \
		$(LOAD_ENV) && .venv/bin/python examples/production_app.py --dry-run; \
	fi
	@if $(MAKE) -s check-gateway 2>/dev/null; then \
		echo "\n=== eval-live ==="; \
		$(LOAD_ENV) && .venv/bin/python -m eval.run_benchmarks --live --quiet; \
		echo "eval-live OK (see eval/results/latest_live.json)"; \
		echo "\n=== FAQ via LiteLLM ==="; \
		$(LOAD_ENV) && .venv/bin/python examples/faq_litellm_gemini.py; \
	else \
		echo "\n=== eval-live + FAQ skipped (start: make gateway) ==="; \
	fi
	@if $(MAKE) -s check-vllm 2>/dev/null; then \
		echo "\n=== phase F live chat ==="; \
		$(LOAD_ENV) && .venv/bin/python examples/phase_f_vllm_chat.py --chat; \
	else \
		echo "\n=== phase F live chat skipped (GPU: make phase-f-up) ==="; \
	fi

run-all: test eval run-demos
	@echo "\nAll targets finished."

run-all-cold: flush-redis run-all
	@echo "\nCold-cache run finished."
