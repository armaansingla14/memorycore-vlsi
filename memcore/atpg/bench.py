"""ISCAS .bench netlist parsing, levelization and Verilog export.

Supported gates: AND, NAND, OR, NOR, XOR, XNOR, NOT, BUF/BUFF, DFF.
For full-scan test, every DFF output becomes a pseudo primary input and
every DFF data input a pseudo primary output (see :meth:`Circuit.comb_view`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

GATE_TYPES = {"AND", "NAND", "OR", "NOR", "XOR", "XNOR", "NOT", "BUF", "DFF"}
_LINE = re.compile(r"^\s*(\S+)\s*=\s*(\w+)\s*\(([^)]*)\)\s*$")


@dataclass
class Gate:
    out: str
    type: str
    ins: list[str]


@dataclass
class Circuit:
    name: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    gates: dict[str, Gate] = field(default_factory=dict)   # keyed by output net
    order: list[str] = field(default_factory=list)          # topological order of comb gates
    flops: list[str] = field(default_factory=list)          # DFF output nets

    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, text: str, name: str = "top") -> "Circuit":
        c = cls(name)
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.match(r"^(INPUT|OUTPUT)\s*\(\s*(\S+)\s*\)$", line, re.I)
            if m:
                (c.inputs if m.group(1).upper() == "INPUT" else c.outputs).append(m.group(2))
                continue
            m = _LINE.match(line)
            if not m:
                raise ValueError(f"cannot parse line: {raw!r}")
            out, typ, args = m.group(1), m.group(2).upper(), m.group(3)
            typ = "BUF" if typ == "BUFF" else typ
            if typ not in GATE_TYPES:
                raise ValueError(f"unsupported gate {typ}")
            ins = [a.strip() for a in args.split(",") if a.strip()]
            if out in c.gates:
                raise ValueError(f"net {out} driven twice")
            c.gates[out] = Gate(out, typ, ins)
            if typ == "DFF":
                c.flops.append(out)
        c._levelize()
        return c

    @classmethod
    def load(cls, path: str | Path) -> "Circuit":
        p = Path(path)
        return cls.parse(p.read_text(), p.stem)

    def _levelize(self):
        sources = set(self.inputs) | set(self.flops)
        done = set(sources)
        comb = [g for g in self.gates.values() if g.type != "DFF"]
        pending = {g.out: g for g in comb}
        order = []
        while pending:
            progressed = False
            for out in list(pending):
                g = pending[out]
                if all(i in done for i in g.ins):
                    order.append(out)
                    done.add(out)
                    del pending[out]
                    progressed = True
            if not progressed:
                raise ValueError(f"combinational loop or undriven net among {sorted(pending)[:5]}")
        self.order = order
        for net in self.outputs + [self.gates[f].ins[0] for f in self.flops]:
            if net not in done:
                raise ValueError(f"undriven net {net}")

    # ------------------------------------------------------------------
    @property
    def pseudo_inputs(self) -> list[str]:
        """Primary inputs followed by scan-flop outputs (full-scan view)."""
        return self.inputs + self.flops

    @property
    def pseudo_outputs(self) -> list[str]:
        """Primary outputs followed by flop data inputs (full-scan view)."""
        return self.outputs + [self.gates[f].ins[0] for f in self.flops]

    def fanout(self) -> dict[str, list[tuple[str, int]]]:
        fo: dict[str, list[tuple[str, int]]] = {}
        for out in self.order:
            for k, i in enumerate(self.gates[out].ins):
                fo.setdefault(i, []).append((out, k))
        return fo

    def n_gates(self) -> int:
        return len(self.order)

    # ------------------------------------------------------------------
    def to_verilog(self, module: str | None = None) -> str:
        """Structural Verilog using primitive gates and a ``dff`` cell."""
        module = module or self.name
        v = _vname
        ports = ["clk"] + [v(i) for i in self.inputs] + [v(o) for o in self.outputs]
        lines = [f"module {module} ({', '.join(ports)});", "  input clk;"]
        lines += [f"  input {v(i)};" for i in self.inputs]
        lines += [f"  output {v(o)};" for o in self.outputs]
        nets = sorted(set(self.gates) - set(self.outputs) - set(self.inputs))
        lines += [f"  wire {v(n)};" for n in nets]
        for k, out in enumerate(self.order):
            g = self.gates[out]
            prim = {"BUF": "buf", "NOT": "not"}.get(g.type, g.type.lower())
            lines.append(f"  {prim} g{k} ({v(out)}, {', '.join(v(i) for i in g.ins)});")
        for k, f in enumerate(self.flops):
            lines.append(f"  dff r{k} (.clk(clk), .d({v(self.gates[f].ins[0])}), .q({v(f)}));")
        lines.append("endmodule")
        return "\n".join(lines) + "\n"


def _vname(n: str) -> str:
    return n if re.fullmatch(r"[A-Za-z_]\w*", n) else "n_" + re.sub(r"\W", "_", n)
