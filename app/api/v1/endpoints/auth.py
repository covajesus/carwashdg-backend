from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.deps import CurrentUserDep, UserServiceDep
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services.user_service import AuthFailedError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, service: UserServiceDep):
    try:
        user_row = service.authenticate(body.email, body.password)
    except AuthFailedError:
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "Credenciales incorrectas"},
        )

    user = service.to_public(user_row)
    token = create_access_token(str(user_row.id), extra={"email": user_row.email})
    return LoginResponse(access_token=token, user=user)


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUserDep) -> MeResponse:
    return MeResponse(user=current_user)


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CarWash DG — Iniciar sesión</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      font-family: system-ui, sans-serif;
      background: linear-gradient(135deg, #f1f5f9, #fff 50%, #e0f2fe);
    }
    .card {
      width: 100%; max-width: 400px; padding: 2rem;
      background: #fff; border-radius: 1rem;
      box-shadow: 0 20px 50px rgba(15,23,42,.12);
      border: 1px solid #e2e8f0;
    }
    h1 { margin: 0 0 .25rem; font-size: 1.35rem; color: #0f172a; }
    p.sub { margin: 0 0 1.5rem; color: #64748b; font-size: .875rem; }
    label { display: block; font-size: .75rem; font-weight: 600; color: #475569; margin-bottom: .35rem; text-transform: uppercase; letter-spacing: .04em; }
    input {
      width: 100%; padding: .75rem 1rem; margin-bottom: 1rem;
      border: 1px solid #cbd5e1; border-radius: .5rem; font-size: 1rem;
    }
    input:focus { outline: none; border-color: #0ea5e9; box-shadow: 0 0 0 3px rgba(14,165,233,.2); }
    button {
      width: 100%; padding: .85rem; border: none; border-radius: .5rem;
      background: #001c68; color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer;
    }
    button:hover { background: #00247e; }
    button:disabled { opacity: .6; cursor: not-allowed; }
    .err { color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; padding: .75rem; border-radius: .5rem; font-size: .875rem; margin-bottom: 1rem; display: none; }
    .ok { color: #166534; background: #f0fdf4; border: 1px solid #bbf7d0; padding: .75rem; border-radius: .5rem; font-size: .8rem; margin-top: 1rem; display: none; word-break: break-all; }
    .hint { margin-top: 1rem; font-size: .75rem; color: #94a3b8; text-align: center; }
  </style>
</head>
<body>
  <div class="card">
    <h1>CarWash DG</h1>
    <p class="sub">API — Iniciar sesión</p>
    <div id="err" class="err"></div>
    <form id="form">
      <label for="email">Correo</label>
      <input id="email" type="email" value="admin@demo.com" required autocomplete="username" />
      <label for="password">Contraseña</label>
      <input id="password" type="password" value="demo123" required autocomplete="current-password" />
      <button type="submit" id="btn">Iniciar sesión</button>
    </form>
    <div id="ok" class="ok"></div>
    <p class="hint">Por defecto: admin@demo.com / demo123<br><a href="/docs">Documentación API</a></p>
  </div>
  <script>
    const form = document.getElementById("form");
    const err = document.getElementById("err");
    const ok = document.getElementById("ok");
    const btn = document.getElementById("btn");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.style.display = "none";
      ok.style.display = "none";
      btn.disabled = true;
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: document.getElementById("email").value,
            password: document.getElementById("password").value,
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          err.textContent = data.error || "Credenciales incorrectas";
          err.style.display = "block";
          return;
        }
        localStorage.setItem("cw_token", data.access_token);
        ok.textContent = "Sesión iniciada. Token guardado en localStorage (cw_token). Usuario: " + data.user.fullName;
        ok.style.display = "block";
      } catch {
        err.textContent = "Error de red";
        err.style.display = "block";
      } finally {
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>"""
