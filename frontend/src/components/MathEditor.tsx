import { useEffect, useRef, useState } from "react";

interface MathEditorProps {
  /** The text already typed, to start from. */
  initial: string;
  onLatex: (latex: string) => void;
  onSubmit: () => void;
}

interface MathField extends HTMLElement {
  getValue: (format?: string) => string;
  setValue: (value: string, options?: { format?: string }) => void;
  mathVirtualKeyboardPolicy: string;
}

interface VirtualKeyboard {
  show: () => void;
  hide: () => void;
  visible: boolean;
}

/**
 * The visual editor (MathLive, ADR 0020), loaded only when it is opened. It
 * uses the KaTeX fonts the page already has and no sounds: nothing comes from
 * outside (ADR 0001). On a touch screen its keyboard opens by itself.
 */
export function MathEditor({ initial, onLatex, onSubmit }: MathEditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onLatex, onSubmit });
  callbacks.current = { onLatex, onSubmit };
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const startWith = useRef(initial);

  useEffect(() => {
    let cancelled = false;
    let field: MathField | null = null;
    import("mathlive")
      .then(({ MathfieldElement }) => {
        if (cancelled || !host.current) {
          return;
        }
        MathfieldElement.fontsDirectory = null; // the KaTeX fonts of the page
        MathfieldElement.soundsDirectory = null;
        field = document.createElement("math-field") as MathField;
        field.setAttribute("aria-label", "Expressão ou equação (editor visual)");
        field.mathVirtualKeyboardPolicy = "auto"; // touch screens only
        field.className = "block w-full text-xl";
        field.addEventListener("input", () => callbacks.current.onLatex(field!.getValue("latex")));
        field.addEventListener("change", () => callbacks.current.onSubmit()); // Enter
        host.current.append(field);
        if (startWith.current) {
          try {
            field.setValue(startWith.current, { format: "ascii-math" });
          } catch {
            // Text the editor cannot read starts empty.
          }
          callbacks.current.onLatex(field.getValue("latex"));
        }
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("failed");
        }
      });
    return () => {
      cancelled = true;
      field?.remove();
    };
  }, []);

  function toggleKeyboard() {
    const keyboard = (window as unknown as { mathVirtualKeyboard?: VirtualKeyboard })
      .mathVirtualKeyboard;
    const field = host.current?.querySelector("math-field") as MathField | null;
    field?.focus();
    if (keyboard) {
      if (keyboard.visible) {
        keyboard.hide();
      } else {
        keyboard.show();
      }
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={host}
        className="min-h-14 rounded-lg border border-slate-500 bg-white px-3 py-2 text-slate-900 shadow-sm"
      >
        {status === "loading" && <p className="text-sm text-slate-500">Carregando o editor…</p>}
        {status === "failed" && (
          <p role="alert" className="text-sm text-rose-700">
            Não foi possível carregar o editor visual. Use o campo de texto.
          </p>
        )}
      </div>
      {status === "ready" && (
        <button
          type="button"
          onClick={toggleKeyboard}
          className="self-start rounded-lg border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50"
        >
          Teclado matemático
        </button>
      )}
    </div>
  );
}
