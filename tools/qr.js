/* Genç - küçük QR kod üretici (bayt kipi, sürüm 1-5, L/M/Q/H). */
(function (root) {
  var EXP = new Array(512), LOG = new Array(256);
  (function () {
    var x = 1;
    for (var i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11d; }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
  })();
  function mul(a, b) { return (a === 0 || b === 0) ? 0 : EXP[LOG[a] + LOG[b]]; }
  function polyMul(a, b) {
    var r = new Array(a.length + b.length - 1);
    for (var i = 0; i < r.length; i++) r[i] = 0;
    for (i = 0; i < a.length; i++) for (var j = 0; j < b.length; j++) r[i + j] ^= mul(a[i], b[j]);
    return r;
  }
  function rsGen(n) { var p = [1]; for (var i = 0; i < n; i++) p = polyMul(p, [1, EXP[i]]); return p; }
  function rsEncode(data, nec) {
    var gen = rsGen(nec), res = data.concat(new Array(nec));
    for (var i = 0; i < res.length; i++) res[i] = res[i] || 0;
    for (i = 0; i < data.length; i++) {
      var coef = res[i];
      if (coef) for (var j = 0; j < gen.length; j++) res[i + j] ^= mul(gen[j], coef);
    }
    return res.slice(data.length);
  }

  var EC_BITS = { L: 1, M: 0, Q: 3, H: 2 };
  var RS = {
    1: { L: [[1, 26, 19]], M: [[1, 26, 16]], Q: [[1, 26, 13]], H: [[1, 26, 9]] },
    2: { L: [[1, 44, 34]], M: [[1, 44, 28]], Q: [[1, 44, 22]], H: [[1, 44, 16]] },
    3: { L: [[1, 70, 55]], M: [[1, 70, 44]], Q: [[2, 35, 17]], H: [[2, 35, 13]] },
    4: { L: [[1, 100, 80]], M: [[2, 50, 32]], Q: [[2, 50, 24]], H: [[4, 25, 9]] },
    5: { L: [[1, 134, 108]], M: [[2, 67, 43]], Q: [[2, 33, 15], [2, 34, 16]], H: [[2, 33, 11], [2, 34, 12]] }
  };
  var ALIGN = { 1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30] };
  var FORMAT_EC = { L: 1, M: 0, Q: 3, H: 2 };

  function utf8Bytes(s) {
    var out = [];
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c < 0x80) out.push(c);
      else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      else if (c >= 0xd800 && c < 0xdc00) {
        var c2 = s.charCodeAt(++i);
        c = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00);
        out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      } else out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return out;
  }

  function dataCodewords(version, level) {
    var g = RS[version][level], n = 0;
    for (var i = 0; i < g.length; i++) n += g[i][0] * g[i][2];
    return n;
  }

  function pickVersion(len, level) {
    for (var v = 1; v <= 5; v++) {
      if (4 + 8 + len * 8 <= dataCodewords(v, level) * 8) return v;
    }
    return 0;
  }

  function encode(text, level) {
    var bytes = utf8Bytes(text);
    var version = pickVersion(bytes.length, level);
    if (!version) throw new Error("QR: veri bu sürüme sığmıyor");
    var cap = dataCodewords(version, level);
    var bits = [];
    function put(val, len) { for (var i = len - 1; i >= 0; i--) bits.push((val >> i) & 1); }
    put(4, 4);
    put(bytes.length, 8);
    for (var i = 0; i < bytes.length; i++) put(bytes[i], 8);
    var maxBits = cap * 8;
    for (i = 0; i < 4 && bits.length < maxBits; i++) bits.push(0);
    while (bits.length % 8) bits.push(0);
    var pads = [0xEC, 0x11], pi = 0;
    while (bits.length < maxBits) { put(pads[pi++ % 2], 8); }
    var cw = [];
    for (i = 0; i < bits.length; i += 8) {
      var b = 0;
      for (var j = 0; j < 8; j++) b = (b << 1) | bits[i + j];
      cw.push(b);
    }
    // bloklara ayır
    var groups = RS[version][level], blocks = [], ecLen = 0, k = 0;
    for (i = 0; i < groups.length; i++) {
      for (var c = 0; c < groups[i][0]; c++) {
        var data = cw.slice(k, k + groups[i][2]); k += groups[i][2];
        blocks.push({ data: data, ec: rsEncode(data, groups[i][1] - groups[i][2]) });
        ecLen = groups[i][1] - groups[i][2];
      }
    }
    var maxData = Math.max.apply(null, blocks.map(function (b) { return b.data.length; }));
    var final = [];
    for (i = 0; i < maxData; i++) for (j = 0; j < blocks.length; j++) if (i < blocks[j].data.length) final.push(blocks[j].data[i]);
    for (i = 0; i < ecLen; i++) for (j = 0; j < blocks.length; j++) final.push(blocks[j].ec[i]);
    return { version: version, level: level, codewords: final };
  }

  // Biçim bilgisi modülleri, LSB'den başlayarak (satır, sütun) sırasıyla.
  function formatCells(size) {
    var c = [];
    for (var i = 0; i < 15; i++) {
      if (i < 6) c.push([i, 8]);
      else if (i < 8) c.push([i + 1, 8]);
      else c.push([size - 15 + i, 8]);
    }
    for (i = 0; i < 15; i++) {
      if (i < 8) c.push([8, size - 1 - i]);
      else if (i < 9) c.push([8, 7]);
      else c.push([8, 14 - i]);
    }
    return c;
  }

  function matrix(text, level) {
    level = level || "M";
    var enc = encode(text, level), version = enc.version;
    var size = version * 4 + 17;
    var m = [], reserved = [];
    for (var i = 0; i < size; i++) { m.push(new Array(size)); reserved.push(new Array(size)); }
    for (i = 0; i < size; i++) for (var j = 0; j < size; j++) { m[i][j] = 0; reserved[i][j] = 0; }

    function set(r, c, v, res) { if (r < 0 || c < 0 || r >= size || c >= size) return; m[r][c] = v; if (res) reserved[r][c] = 1; }

    function finder(r, c) {
      for (var dr = -1; dr <= 7; dr++) for (var dc = -1; dc <= 7; dc++) {
        var rr = r + dr, cc = c + dc;
        if (rr < 0 || cc < 0 || rr >= size || cc >= size) continue;
        var inRing = dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6;
        var dark = inRing && (dr === 0 || dr === 6 || dc === 0 || dc === 6 || (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4));
        set(rr, cc, dark ? 1 : 0, true);
      }
    }
    finder(0, 0); finder(0, size - 7); finder(size - 7, 0);

    for (i = 8; i < size - 8; i++) { var t = (i % 2 === 0) ? 1 : 0; set(6, i, t, true); set(i, 6, t, true); }

    var centers = ALIGN[version];
    for (var a = 0; a < centers.length; a++) for (var b = 0; b < centers.length; b++) {
      var cr = centers[a], cc2 = centers[b];
      if ((cr <= 8 && cc2 <= 8) || (cr <= 8 && cc2 >= size - 9) || (cr >= size - 9 && cc2 <= 8)) continue;
      for (var dr2 = -2; dr2 <= 2; dr2++) for (var dc2 = -2; dc2 <= 2; dc2++) {
        var dark2 = Math.max(Math.abs(dr2), Math.abs(dc2)) !== 1;
        set(cr + dr2, cc2 + dc2, dark2 ? 1 : 0, true);
      }
    }

    set(size - 8, 8, 1, true); // koyu modül
    var fmtCells = formatCells(size);
    for (i = 0; i < fmtCells.length; i++) { set(fmtCells[i][0], fmtCells[i][1], 0, true); }

    // veri yerleştirme (zikzak)
    var bitIdx = 0, total = enc.codewords.length * 8;
    function nextBit() { var byte = enc.codewords[bitIdx >> 3]; var bit = (byte >> (7 - (bitIdx & 7))) & 1; bitIdx++; return bit; }
    var up = true;
    for (var col = size - 1; col > 0; col -= 2) {
      if (col === 6) col--;
      for (var row = 0; row < size; row++) {
        var r2 = up ? size - 1 - row : row;
        for (var c2 = 0; c2 < 2; c2++) {
          var cc3 = col - c2;
          if (!reserved[r2][cc3]) m[r2][cc3] = bitIdx < total ? nextBit() : 0;
        }
      }
      up = !up;
    }

    function maskFn(id, r, c) {
      switch (id) {
        case 0: return (r + c) % 2 === 0;
        case 1: return r % 2 === 0;
        case 2: return c % 3 === 0;
        case 3: return (r + c) % 3 === 0;
        case 4: return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0;
        case 5: return ((r * c) % 2) + ((r * c) % 3) === 0;
        case 6: return (((r * c) % 2) + ((r * c) % 3)) % 2 === 0;
        default: return (((r + c) % 2) + ((r * c) % 3)) % 2 === 0;
      }
    }
    function applyMask(id) {
      for (var r = 0; r < size; r++) for (var c = 0; c < size; c++) if (!reserved[r][c] && maskFn(id, r, c)) m[r][c] ^= 1;
    }
    function penalty() {
      var p = 0, r, c, run, dark = 0;
      for (r = 0; r < size; r++) {
        run = 1;
        for (c = 1; c < size; c++) { if (m[r][c] === m[r][c - 1]) run++; else { if (run >= 5) p += run - 2; run = 1; } }
        if (run >= 5) p += run - 2;
      }
      for (c = 0; c < size; c++) {
        run = 1;
        for (r = 1; r < size; r++) { if (m[r][c] === m[r - 1][c]) run++; else { if (run >= 5) p += run - 2; run = 1; } }
        if (run >= 5) p += run - 2;
      }
      for (r = 0; r < size - 1; r++) for (c = 0; c < size - 1; c++) {
        var s = m[r][c] + m[r][c + 1] + m[r + 1][c] + m[r + 1][c + 1];
        if (s === 0 || s === 4) p += 3;
      }
      var pat = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
      function hasPat(get, len) {
        var n = 0;
        for (var s = 0; s + 11 <= len; s++) {
          var ok = true, ok2 = true;
          for (var k = 0; k < 11; k++) { if (get(s + k) !== pat[k]) ok = false; }
          for (k = 0; k < 11; k++) { if (get(s + k) !== pat[10 - k]) ok2 = false; }
          if (ok || ok2) n++;
        }
        return n;
      }
      for (r = 0; r < size; r++) p += 40 * hasPat((function (rr) { return function (i) { return m[rr][i]; }; })(r), size);
      for (c = 0; c < size; c++) p += 40 * hasPat((function (cc) { return function (i) { return m[i][cc]; }; })(c), size);
      for (r = 0; r < size; r++) for (c = 0; c < size; c++) if (m[r][c]) dark++;
      var pct = dark * 100 / (size * size);
      p += 10 * Math.floor(Math.abs(pct - 50) / 5);
      return p;
    }

    var best = 0, bestScore = Infinity, snapshot;
    for (var mid = 0; mid < 8; mid++) {
      applyMask(mid);
      var sc = penalty();
      if (sc < bestScore) { bestScore = sc; best = mid; }
      applyMask(mid);
    }
    applyMask(best);

    // biçim bilgisi
    var fmtData = (FORMAT_EC[level] << 3) | best, rem = fmtData;
    for (i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >> 9) * 0x537);
    var fmt = ((fmtData << 10) | rem) ^ 0x5412;
    for (i = 0; i < fmtCells.length; i++) set(fmtCells[i][0], fmtCells[i][1], (fmt >> (i % 15)) & 1, true);
    set(size - 8, 8, 1, true);

    return m;
  }

  root.QRCodeLite = { matrix: matrix, encode: encode };
})(typeof module !== "undefined" && module.exports ? module.exports : (typeof globalThis !== "undefined" ? globalThis : this));
