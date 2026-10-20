"""환경음 합성(바람·파도·새·풍경·범종) → out/ambience.wav (48kHz 스테레오, 녹음 소스 없이 코드로 생성).
실행: /opt/bvenv/bin/python final/audio_synth.py [--seconds 24] [--out out/ambience.wav]
"""
import argparse
import os

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
rng = np.random.default_rng(1592)  # 1592 = 임진왜란, 시드 고정


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def lowpass(x, hi, order=2):
    return sosfilt(butter(order, hi, btype="low", fs=SR, output="sos"), x)


def smooth_noise(n, rate_hz):
    """느리게 변하는 0..1 엔벨로프(바람 세기 등)."""
    k = max(2, int(n / SR * rate_hz) + 2)
    pts = rng.random(k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)


def wind(n):
    out = np.zeros((n, 2))
    for ch in range(2):
        w = rng.standard_normal(n)
        gust = 0.35 + 0.65 * smooth_noise(n, 0.25) ** 1.5
        low = lowpass(w, 380) * 1.6
        whistle = bandpass(rng.standard_normal(n), 600 + 250 * ch, 1100 + 250 * ch) * smooth_noise(n, 0.5) * 0.5
        out[:, ch] = (low + whistle) * gust
    return out * 0.22


def waves(n):
    """선체에 부딪히는 잔물결: 저역 노이즈 + 4~6초 주기 스웰."""
    out = np.zeros((n, 2))
    t = np.arange(n) / SR
    for ch in range(2):
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * t / (5.3 + ch * 0.7) + ch)
        lap = bandpass(rng.standard_normal(n), 150, 1800) * swell ** 3
        out[:, ch] = lap
    return out * 0.18


def bird_chirp(dur, f0, f1, vib=0.0):
    m = int(dur * SR)
    t = np.arange(m) / SR
    f = np.linspace(f0, f1, m) * (1 + vib * np.sin(2 * np.pi * 28 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.sin(np.pi * np.linspace(0, 1, m)) ** 2
    return (np.sin(ph) + 0.25 * np.sin(2 * ph)) * env


def gull_call(dur):
    """갈매기 'kyow': 하강 글리산도 + 거친 배음."""
    m = int(dur * SR)
    t = np.arange(m) / SR
    f = 1500 * np.exp(-t * 2.2) + 650
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.minimum(1, t * 40) * np.exp(-t * 3.5)
    sig = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)
    return lowpass(np.tanh(2.0 * sig), 5000, 4) * env * 0.6  # tanh 배음 앨리어싱 제거


def birds(n):
    out = np.zeros((n, 2))
    t_cur = 0.8
    while t_cur < n / SR - 1.5:
        pan = rng.uniform(-0.8, 0.8)
        if rng.random() < 0.3:
            s = gull_call(rng.uniform(0.5, 0.8))
        else:  # 작은 새 2~5연음
            parts = []
            for _ in range(rng.integers(2, 6)):
                f0 = rng.uniform(2800, 4800)
                parts.append(bird_chirp(rng.uniform(0.05, 0.12), f0, f0 * rng.uniform(0.7, 1.4), vib=0.03))
                parts.append(np.zeros(int(rng.uniform(0.03, 0.09) * SR)))
            s = np.concatenate(parts)
        i = int(t_cur * SR)
        j = min(n, i + len(s))
        g = rng.uniform(0.05, 0.12)
        out[i:j, 0] += s[: j - i] * g * (1 - pan) / 2
        out[i:j, 1] += s[: j - i] * g * (1 + pan) / 2
        t_cur += rng.uniform(1.2, 3.5)
    return out


def chime_strike(dur, f0):
    """풍경(작은 금속 종): 비조화 배음 + 빠른 감쇠."""
    m = int(dur * SR)
    t = np.arange(m) / SR
    ratios = [1.0, 2.76, 5.40, 8.93]
    decay = [1.6, 2.6, 4.5, 7.0]
    s = sum(np.sin(2 * np.pi * f0 * r * t + rng.random() * 6) * np.exp(-t * d) / (k + 1)
            for k, (r, d) in enumerate(zip(ratios, decay)))
    return lowpass(s, 9000, 4) * np.minimum(1, t * 3000)


def wind_chimes(n, wind_env):
    out = np.zeros((n, 2))
    t_cur = 2.0
    while t_cur < n / SR - 0.5:
        i = int(t_cur * SR)
        if rng.random() < 0.3 + 0.7 * wind_env[i]:
            s = chime_strike(4.0, rng.choice([1318.5, 1567.98, 1760.0]) * rng.uniform(0.995, 1.005))
            j = min(n, i + len(s))
            out[i:j, 0] += s[: j - i] * 0.05
            out[i:j, 1] += s[: j - i] * 0.07
        t_cur += rng.uniform(0.6, 2.4)
    return out


def temple_bell(n, at_s, f0=64.0):
    """범종(성덕대왕신종류): 저음 기본음 + 비조화 배음, 근접 주파수 쌍의 맥놀이(~0.3Hz), 긴 여운."""
    out = np.zeros(n)
    i0 = int(at_s * SR)
    t = np.arange(n - i0) / SR
    partials = [(0.5, 1.0, 0.05), (1.0, 0.9, 0.10), (1.19, 0.5, 0.15), (1.48, 0.45, 0.22),
                (2.0, 0.35, 0.3), (2.52, 0.25, 0.45), (3.25, 0.15, 0.7), (4.1, 0.1, 1.0)]
    s = np.zeros_like(t)
    for r, a, d in partials:
        f = f0 * r
        beat = 0.32 * r ** 0.5
        s += a * (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * (f + beat) * t)) * 0.5 * np.exp(-t * d)
    strike = bandpass(rng.standard_normal(len(t)), 80, 900) * np.exp(-t * 25) * 0.6  # 당목 타격음
    out[i0:] = (s + strike) * np.minimum(1, t * 200)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=24.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "ambience.wav"))
    a = ap.parse_args()
    n = int(a.seconds * SR)
    wenv = smooth_noise(n, 0.25)
    mix = wind(n) + waves(n) + birds(n) + wind_chimes(n, wenv)
    bell = sum(temple_bell(n, t0) for t0 in (1.5, 13.0))
    mix += np.stack([bell, bell * 0.92], axis=1) * 0.22
    fade = np.ones(n)
    fl = int(1.5 * SR)
    fade[:fl] = np.linspace(0, 1, fl)
    fade[-fl:] = np.linspace(1, 0, fl)
    mix *= fade[:, None]
    mix /= np.max(np.abs(mix)) / 0.89  # -1 dBFS 피크 정규화
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    wavfile.write(a.out, SR, (mix * 32767).astype(np.int16))
    print("wrote", a.out, f"{a.seconds}s")


if __name__ == "__main__":
    main()
