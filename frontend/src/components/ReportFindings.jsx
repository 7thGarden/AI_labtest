import {
  Activity,
  FileSearch,
  HelpCircle,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  Users,
} from "lucide-react";
import { stripAnsi } from "../utils/opensre";
import { parseFindings } from "../utils/reportMd";

const SECTION_META = {
  "incident command": { label: "On-call triage", icon: Users },
  "findings": { label: "Findings", icon: FileSearch },
  "hypotheses": { label: "Hypotheses", icon: Lightbulb },
  "verification": { label: "Verification performed", icon: ShieldCheck },
  "follow-up questions": { label: "Open questions", icon: HelpCircle },
  "summary": { label: "Summary", icon: ListChecks },
  "impact": { label: "Impact", icon: Activity },
  "remediation": { label: "Remediation trade-offs", icon: Activity },
  "evidence": { label: "Evidence", icon: ListChecks },
};

const SKIP_PREFIXES = ["recommended action", "recommendation", "cited evidence"];

function sectionMeta(title = "") {
  const key = String(title).trim().toLowerCase();

  for (const [candidate, meta] of Object.entries(SECTION_META)) {
    if (key === candidate || key.startsWith(candidate)) return meta;
  }

  return { label: String(title).trim(), icon: Activity };
}

function Inline({ text }) {
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);

  return (
    <>
      {parts.map((part, index) => {
        if (!part) return null;

        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        }

        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={index} className="inline-code">
              {part.slice(1, -1)}
            </code>
          );
        }

        return <span key={index}>{part}</span>;
      })}
    </>
  );
}

function BlockList({ blocks }) {
  return (
    <>
      {blocks.map((block, index) => {
        if (block.type === "paragraph") {
          return (
            <p key={index} className="findings__text">
              <Inline text={block.text} />
            </p>
          );
        }

        if (block.type === "kv") {
          return (
            <div key={index} className="findings__kvs">
              {block.items.map((item, itemIndex) => (
                <span key={itemIndex} className="findings__kv">
                  {item.key && (
                    <span className="findings__kv-key">{item.key}</span>
                  )}
                  <Inline text={item.value} />
                </span>
              ))}
            </div>
          );
        }

        const ordered = block.kind === "ordered";
        let number = 0;

        return (
          <ul
            key={index}
            className={ordered ? "findings__list findings__list--num" : "findings__list"}
          >
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex}>
                {ordered ? (
                  <span className="findings__num">{++number}</span>
                ) : (
                  <span className="findings__dot" />
                )}
                <span>
                  <Inline text={item} />
                </span>
              </li>
            ))}
          </ul>
        );
      })}
    </>
  );
}

export default function ReportFindings({ markdown }) {
  const sections = parseFindings(stripAnsi(markdown || "")).filter(
    (section) => {
      if (!section.title.trim()) return false;

      const title = section.title.toLowerCase();
      return !SKIP_PREFIXES.some((prefix) => title.startsWith(prefix));
    }
  );

  if (sections.length === 0) {
    return <p className="findings__text">{stripAnsi(markdown || "")}</p>;
  }

  return (
    <div className="findings">
      {sections.map((section, index) => {
        const meta = sectionMeta(section.title || "Findings");
        const Icon = meta.icon;

        return (
          <section className="findings__section" key={index}>
            <div className="findings__head">
              <span className="findings__icon">
                <Icon size={15} />
              </span>
              <h3 className="findings__title">{meta.label}</h3>
            </div>
            <div className="findings__body">
              <BlockList blocks={section.blocks} />
            </div>
          </section>
        );
      })}
    </div>
  );
}