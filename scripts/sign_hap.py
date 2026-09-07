# -*- coding: utf-8 -*-
"""
本地调试签名：用 DevEco 自带 hap-sign-tool.jar 生成自签调试证书链（全部 key 放同一个
p12），把 unsigned HAP 签成 debug 包，不依赖华为账号/IDE 自动签名。

已按本机 hap-sign-tool 的 `-h` 实际参数表重写（generate-ca 系列没有 -keyOutFile 等字段）。
用法:
  python scripts/sign_hap.py --hap <unsigned.hap> [--bundle com.bench.code] --out C:/benchdata/signed
"""
import argparse
import base64 as _b64
import json
import subprocess
from pathlib import Path

DEVECO_DEFAULT = Path("G:/360downloads/DevEco Studio")
SIGN_DIR = Path("C:/benchdata/sign")
KS_PWD = "123456"


def find_java(devdir: Path) -> Path:
    j = devdir / "jbr" / "bin" / "java.exe"
    if not j.exists():
        raise SystemExit(f"未找到 {j}")
    return j


def jar(devdir: Path) -> str:
    p = devdir / "sdk" / "default" / "openharmony" / "toolchains" / "lib" / "hap-sign-tool.jar"
    if not p.exists():
        raise SystemExit(f"未找到 {p}")
    return str(p)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"失败({r.returncode}): {' '.join(cmd[:6])}\n{r.stdout[-600:]}\n{r.stderr[-600:]}")
    return r


def ensure_chain(devdir: Path):
    java, j = find_java(devdir), jar(devdir)
    SIGN_DIR.mkdir(parents=True, exist_ok=True)
    ks = str(SIGN_DIR / "bench.p12")
    root_c = str(SIGN_DIR / "rootCA.cer")
    sub_app_c = str(SIGN_DIR / "subAppCA.cer")
    sub_pro_c = str(SIGN_DIR / "subProfileCA.cer")
    app_c = str(SIGN_DIR / "app.cer")
    prof_c = str(SIGN_DIR / "prof.cer")

    def hs(*a):
        return run([str(java), "-jar", j] + list(a))

    if not Path(root_c).exists():
        hs("generate-ca", "-keyAlias", "benchRoot", "-keyAlg", "ECC", "-keySize", "NIST-P-256",
           "-subject", "C=CN,O=bench,CN=Bench Root CA", "-validity", "3650",
           "-signAlg", "SHA256withECDSA", "-keystoreFile", ks, "-keystorePwd", KS_PWD,
           "-outFile", root_c)
    for alias, subject, issuer_alias, out in [
        ("benchSubApp", "C=CN,O=bench,CN=Bench App Sub CA", "benchRoot", sub_app_c),
        ("benchSubPro", "C=CN,O=bench,CN=Bench Profile Sub CA", "benchRoot", sub_pro_c),
    ]:
        if not Path(out).exists():
            hs("generate-ca", "-keyAlias", alias, "-keyAlg", "ECC", "-keySize", "NIST-P-256",
               "-issuer", "C=CN,O=bench,CN=Bench Root CA", "-issuerKeyAlias", issuer_alias,
               "-subject", subject, "-validity", "3650",
               "-signAlg", "SHA256withECDSA", "-keystoreFile", ks, "-keystorePwd", KS_PWD,
               "-outFile", out)
    if not Path(app_c).exists():
        hs("generate-keypair", "-keyAlias", "bench", "-keyPwd", KS_PWD, "-keyAlg", "ECC",
           "-keySize", "NIST-P-256", "-keystoreFile", ks, "-keystorePwd", KS_PWD)
        hs("generate-app-cert", "-keyAlias", "bench", "-keyPwd", KS_PWD,
           "-issuer", "C=CN,O=bench,CN=Bench App Sub CA", "-issuerKeyAlias", "benchSubApp",
           "-subject", "C=CN,O=bench,CN=Bench App",
           "-validity", "3650", "-signAlg", "SHA256withECDSA",
           "-rootCaCertFile", root_c, "-subCaCertFile", sub_app_c,
           "-keystoreFile", ks, "-keystorePwd", KS_PWD, "-outForm", "certChain", "-outFile", app_c)
    if not Path(prof_c).exists():
        hs("generate-keypair", "-keyAlias", "benchPro", "-keyPwd", KS_PWD, "-keyAlg", "ECC",
           "-keySize", "NIST-P-256", "-keystoreFile", ks, "-keystorePwd", KS_PWD)
        hs("generate-profile-cert", "-keyAlias", "benchPro", "-keyPwd", KS_PWD,
           "-issuer", "C=CN,O=bench,CN=Bench Profile Sub CA", "-issuerKeyAlias", "benchSubPro",
           "-subject", "C=CN,O=bench,CN=Bench Profile",
           "-validity", "3650", "-signAlg", "SHA256withECDSA",
           "-rootCaCertFile", root_c, "-subCaCertFile", sub_pro_c,
           "-keystoreFile", ks, "-keystorePwd", KS_PWD, "-outForm", "certChain", "-outFile", prof_c)
    return java, j, ks, app_c, prof_c


PROFILE_TMPL = {
    "version-name": "2.0.0",
    "version-code": 2,
    "app-distribution-type": "os_integration",
    "uuid": "bench-debug-profile-0001",
    "validity": {"not-before": 1680000000000, "not-after": 253402300799000},
    "type": "debug",
    "bundle-info": {
        "developer-id": "bench",
        "distribution-certificate": "C=CN,O=bench,CN=Bench App",
        "bundle-name": "{bundle}",
        "bundle-type": "app",
    },
}


def sign_one(hap: Path, out_dir: Path, devdir: Path, bundle: str) -> Path:
    java, j, ks, app_c, prof_c = ensure_chain(devdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_json = SIGN_DIR / ("profile_%s.json" % bundle.replace(".", "_"))
    tmpl = dict(PROFILE_TMPL)
    app_cert_b64 = _b64.b64encode(Path(app_c).read_bytes()).decode("ascii")
    tmpl["bundle-info"] = dict(PROFILE_TMPL["bundle-info"],
                               **{"bundle-name": bundle, "distribution-certificate": app_cert_b64,
                                  "development-certificate": app_cert_b64})
    profile_json.write_text(json.dumps(tmpl, ensure_ascii=False, indent=2), encoding="utf-8")
    p7b = SIGN_DIR / ("profile_%s.p7b" % bundle.replace(".", "_"))

    run([str(java), "-jar", j, "sign-profile", "-mode", "localSign", "-keyAlias", "benchPro",
         "-keyPwd", KS_PWD, "-profileCertFile", prof_c, "-inFile", str(profile_json),
         "-signAlg", "SHA256withECDSA", "-keystoreFile", ks, "-keystorePwd", KS_PWD,
         "-outFile", str(p7b)])
    out_hap = out_dir / (bundle + "-signed.hap")
    run([str(java), "-jar", j, "sign-app", "-mode", "localSign", "-keyAlias", "bench",
         "-keyPwd", KS_PWD, "-appCertFile", app_c, "-profileFile", str(p7b),
         "-inFile", str(hap), "-signAlg", "SHA256withECDSA", "-keystoreFile", ks,
         "-keystorePwd", KS_PWD, "-outFile", str(out_hap)])
    # TODO-verify-at-device：verify-app 的 outCertChain 所需扩展名未明（.pem/.json 均被拒），
    # 安装校验留待 hdc install 在模拟器/真机上进行。
    return out_hap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hap", required=True)
    ap.add_argument("--bundle", default=None)
    ap.add_argument("--out", default="C:/benchdata/signed")
    ap.add_argument("--deveco", default=str(DEVECO_DEFAULT))
    args = ap.parse_args()
    devdir = Path(args.deveco)
    hap = Path(args.hap)
    bundle = args.bundle
    if not bundle:
        for probe in list(hap.parents) + [Path("apps") / (hap.parent.name)]:
            if (probe / "task.json").exists():
                bundle = json.loads((probe / "task.json").read_text(encoding="utf-8")).get("app_bundle")
                break
        # 兜底：从输出目录缓存推断
        if not bundle:
            for probe in list(hap.parents):
                if (probe / "variant.json").exists():
                    bundle = json.loads((probe / "variant.json").read_text(encoding="utf-8")).get("bundle")
                    break
    if not bundle:
        raise SystemExit("未能推断包名，请用 --bundle 指定")
    out = sign_one(hap, Path(args.out), devdir, bundle)
    print(f"[sign] {hap.name} → {out}")


if __name__ == "__main__":
    main()