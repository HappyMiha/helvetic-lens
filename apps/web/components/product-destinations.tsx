import { ArrowUpRight, Check } from "lucide-react";
import {
  productDestinations,
  productNavigationCopy,
  type ProductName,
} from "../lib/product-navigation";

export function ProductDestinations({
  current,
  copy = productNavigationCopy["en-CH"],
}: {
  current: ProductName;
  copy?: (typeof productNavigationCopy)["en-CH"];
}) {
  return (
    <section className="hl-products" aria-label={copy.title}>
      <p className="hl-products-title">{copy.title}</p>
      <ul>
        {productDestinations.map((destination) => (
          <li key={destination.id}>
            {destination.id === current ? (
              <span className="hl-product-current" aria-current="true">
                <strong>{destination.name}</strong>
                <small>{copy.current}</small>
                <Check size={15} aria-hidden="true" />
              </span>
            ) : (
              <a
                href={destination.href}
                target="_blank"
                rel="noopener noreferrer"
                referrerPolicy="no-referrer"
                aria-label={`${destination.name} · ${copy.opens}`}
              >
                <strong>{destination.name}</strong>
                <ArrowUpRight size={16} aria-hidden="true" />
              </a>
            )}
          </li>
        ))}
      </ul>
      <p className="hl-products-note">{copy.note}</p>
    </section>
  );
}
