from __future__ import annotations
import base64
import json
import os
from datetime import datetime, timezone
import typer

app = typer.Typer(help="Safe local diagnostics for Dhan data configuration")


def _decode_jwt_payload_no_verify(token: str) -> dict:
    """Decode JWT payload without verifying signature.

    This is only for local diagnostics such as checking exp/iat. It never authenticates a request.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Token is not in JWT format")
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))


@app.command()
def credentials():
    client_id = os.getenv("DHAN_CLIENT_ID")
    token = os.getenv("DHAN_ACCESS_TOKEN")
    if client_id:
        typer.echo("DHAN_CLIENT_ID: set")
    else:
        typer.echo("DHAN_CLIENT_ID: missing")
    if not token:
        typer.echo("DHAN_ACCESS_TOKEN: missing")
        raise typer.Exit(1)
    typer.echo("DHAN_ACCESS_TOKEN: set")
    try:
        payload = _decode_jwt_payload_no_verify(token)
    except Exception as exc:
        typer.echo(f"Token diagnostic: unable to decode JWT payload safely: {exc}")
        raise typer.Exit(1)

    now = datetime.now(timezone.utc)
    exp = payload.get("exp")
    iat = payload.get("iat")
    dhan_client = payload.get("dhanClientId") or payload.get("dhanClientId".lower()) or payload.get("dhanClientId")
    if iat:
        typer.echo(f"Token issued at UTC: {datetime.fromtimestamp(int(iat), tz=timezone.utc).isoformat()}")
    if exp:
        exp_dt = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        typer.echo(f"Token expires at UTC: {exp_dt.isoformat()}")
        typer.echo(f"Token status: {'EXPIRED' if exp_dt <= now else 'valid by exp claim'}")
        if exp_dt <= now:
            typer.echo("Recommended action: regenerate the Dhan access token and update DHAN_ACCESS_TOKEN.")
            raise typer.Exit(2)
    else:
        typer.echo("Token diagnostic: no exp claim found")
    if dhan_client:
        typer.echo(f"Token dhanClientId claim: {dhan_client}")
    if client_id and dhan_client and str(client_id) != str(dhan_client):
        typer.echo("WARNING: DHAN_CLIENT_ID does not match token dhanClientId claim")
        raise typer.Exit(3)


if __name__ == "__main__":
    app()
