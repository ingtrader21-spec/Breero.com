import Link from "next/link";
import type { ServiceAreaProjection } from "../../lib/types";
import { Empty, Notice, Panel } from "../ui";

export function ServiceAreasView({ data }: { data: ServiceAreaProjection }) {
  return (
    <div className="ops-stack">
      <Notice>{data.privacy}</Notice>
      {data.unzoned_active_jobs > 0 && (
        <Notice>{data.unzoned_active_jobs} active job(s) have an address outside every configured service zone.</Notice>
      )}
      <Panel title="Service zones">
        {data.areas.length === 0 ? <Empty>No service zones are configured.</Empty> : (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th scope="col">Zone</th>
                  <th scope="col">Region</th>
                  <th scope="col">State</th>
                  <th scope="col" className="ops-num">ZIP codes</th>
                  <th scope="col" className="ops-num">Active jobs</th>
                  <th scope="col" className="ops-num">Unassigned</th>
                  <th scope="col" className="ops-num">Dispatchable workers</th>
                </tr>
              </thead>
              <tbody>
                {data.areas.map((area) => {
                  const uncovered = area.active && area.active_jobs > 0 && area.covering_dispatchable_workers === 0;
                  return (
                    <tr key={area.service_area_id ?? area.name} className={uncovered ? "ops-row--high" : undefined}>
                      <td>
                        {area.service_area_id ? <Link href={`/queue?service_area_id=${area.service_area_id}`}>{area.name}</Link> : area.name}
                        {!area.active && <span className="ops-tag">Inactive</span>}
                        {area.emergency_enabled && <span className="ops-tag">Emergency</span>}
                      </td>
                      <td>{[area.city, area.country_code].filter(Boolean).join(", ") || "—"}</td>
                      <td>{area.state_code ?? "—"}</td>
                      <td className="ops-num">{area.postal_code_count}</td>
                      <td className="ops-num">{area.active_jobs}</td>
                      <td className="ops-num">{area.unassigned_jobs}</td>
                      <td className="ops-num">
                        {area.covering_dispatchable_workers}
                        {uncovered && <span className="ops-tag ops-tag--alert">Jobs without dispatchable workers</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
