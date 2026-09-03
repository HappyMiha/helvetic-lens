import Link from "next/link";
import { ArrowRight, Globe2, ListChecks, Sparkles } from "lucide-react";

export default function OnboardingPage() {
  return (
    <main className="min-h-screen bg-[#f3f3ee] p-6 grid place-items-center">
      <section className="w-full max-w-3xl rounded-[28px] border border-[#dfe3da] bg-white p-8 md:p-12 shadow-[0_24px_80px_rgba(31,45,36,.1)]">
        <span className="eyebrow">YOUR WORKSPACE IS READY</span>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-.04em] text-[#17231f]">Start with one law you care about</h1>
        <p className="mt-4 max-w-2xl leading-7 text-[#68736b]">
          Add an official document URL. Helvetic Lens saves the current version as evidence, then future scans show what changed and what may matter to your organization.
        </p>
        <div className="mt-9 grid gap-4 md:grid-cols-3">
          {[
            [Globe2, "Connect", "Add a Fedlex law or a source website."],
            [ListChecks, "Compare", "Import an earlier version when you have one."],
            [Sparkles, "Understand", "Use local Apertus only after exact changes exist."],
          ].map(([Icon, title, description]) => (
            <div key={String(title)} className="rounded-2xl border border-[#e2e5dd] bg-[#fafaf7] p-5">
              <Icon className="text-[#c94a37]" size={22} />
              <strong className="mt-4 block text-[#22312b]">{String(title)}</strong>
              <p className="mt-2 text-sm leading-6 text-[#717b74]">{String(description)}</p>
            </div>
          ))}
        </div>
        <div className="mt-9 flex flex-wrap gap-3">
          <Link href="/sources" className="inline-flex items-center gap-2 rounded-xl bg-[#cf4936] px-5 py-3 font-medium text-white">
            Add my first law <ArrowRight size={17} />
          </Link>
          <Link href="/" className="inline-flex items-center rounded-xl border border-[#d9ddd4] px-5 py-3 font-medium text-[#39483f]">
            Explore the registry
          </Link>
        </div>
      </section>
    </main>
  );
}
