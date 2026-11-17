"""Una medición de extremo a extremo por revisión, independiente de sus intentos."""

from datetime import datetime

from ivostock.db import execute


def superseded(conn, link_id, revision):
    execute(
        conn,
        "UPDATE publication_measurements SET superseded_at=clock_timestamp() "
        "WHERE link_id=:l AND revision!=:r AND confirmed_at IS NULL AND superseded_at IS NULL",
        l=link_id,
        r=revision,
    )


def requested(conn, link, revision):
    execute(
        conn,
        "INSERT INTO publication_measurements(link_id,revision,store_id,origin_at) "
        "VALUES (:l,:r,:s,CASE WHEN CAST(:run AS bigint) IS NULL THEN clock_timestamp() "
        "ELSE GREATEST((SELECT finished_at FROM runs WHERE id=:run),"
        "(SELECT created_at FROM links WHERE id=:l)) END) "
        "ON CONFLICT(link_id,revision) DO NOTHING",
        l=link["id"],
        r=revision,
        s=link["store_id"],
        run=link.get("run_id"),
    )


def applied(conn, link_id, revision, response):
    # El simulador devuelve el primer efecto de la revisión, incluso si se perdió su acuse.
    # Sin ese dato no se inventa una duración a partir del tiempo de un intento.
    try:
        effect = datetime.fromisoformat(response.json()["effect_at"])
        if effect.tzinfo is None:
            effect = None
    except (ValueError, TypeError, KeyError):
        effect = None
    execute(
        conn,
        "UPDATE publication_measurements SET effect_at=COALESCE(effect_at,:at),"
        "confirmed_at=COALESCE(confirmed_at,clock_timestamp()) "
        "WHERE link_id=:l AND revision=:r",
        at=effect,
        l=link_id,
        r=revision,
    )
