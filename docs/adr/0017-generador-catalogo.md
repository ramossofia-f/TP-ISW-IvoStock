---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0017 — Generador de catálogo para el marketplace simulado

## Context and Problem Statement

El simulador necesita publicaciones suficientes para probar matching, publicación y capacidad sin usar cuentas productivas. RF-36 identifica un generador específico para construir ese catálogo.

## Decision Drivers

* SKU tomados del feed real para ejercitar coincidencias.
* Dos tiendas y 100.000 vínculos totales como carga objetivo del MVP (RNF-13).
* Fallas y latencia reproducibles sin credenciales externas.

## Considered Options

* **Opción A** — Generador configurable que inicializa el simulador.
* **Opción B** — Catálogo fijo pequeño, cargado a mano.

## Decision Outcome

Chosen option: "Opción A — generador configurable", porque permite variar tiendas, publicaciones y proporción de SKU coincidentes sin editar código. Usa semilla registrada, toma SKU del feed y genera atributos sintéticos. Configura publicaciones muertas y los parámetros de latencia y error del simulador.

Se ejecuta bajo demanda. El perfil de capacidad registra por separado vínculos y deltas; generar 100.000 vínculos no acredita por sí solo RNF-01. La cuota del simulador sigue siendo 60 llamadas/minuto por tienda.

### Consequences

* Good, porque la misma herramienta prepara demos, matching y pruebas de volumen.
* Bad, porque el catálogo generado no valida atributos ni comportamiento de publicaciones reales.

### Confirmation

* Repetir la semilla, comprobar volumen y coincidencias y preparar dos tiendas con 50.000 vínculos cada una para M8.

## Pros and Cons of the Options

* **A:** adapta volumen y escenarios; requiere validar los datos generados.
* **B:** simplifica una demo inicial; no sirve para demostrar capacidad ni diversidad de fallas.

## More Information

* [PRD](../prd/PRD.md): RF-35, RF-36 y RNF-13; [roadmap](../roadmap/ROADMAP.md): P1 y M8.
* [Marketplace simulado](0001-marketplace-simulado-detras-de-interfaz.md).
