"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Drawer,
  ErrorState,
  FormField,
  Input,
  LoadingState,
  SearchInput,
  Select,
} from "@breero/ui";
import type {
  AccessAssignmentInput,
  AccessCatalog,
  AccessRole,
  Department,
  PortalContext,
  TenantScope,
} from "@breero/types";
import { customerApi } from "@/lib/customer/api";
import { safeCustomerError } from "@/lib/customer/errors";
import { loadPortalContext } from "@/lib/portal";
import {
  assignmentLabel,
  assignmentsFromContext,
  isValidUserId,
  validateAccessAssignments,
} from "./access-assignment-model";
import styles from "./portal-dashboard.module.css";

const initialAssignment: AccessAssignmentInput = {
  role: "support",
  department: "customer_support",
  tenant_scope: "brand",
  vendor_id: null,
  is_primary: true,
};

const label = (value: string) => value
  .replaceAll("_", " ")
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

type OperationState = "loading" | "idle" | "loading-profile" | "saving" | "success" | "error";

export function AccessAssignmentForm() {
  const [catalog, setCatalog] = useState<AccessCatalog | null>(null);
  const [operatorContext, setOperatorContext] = useState<PortalContext | null>(null);
  const [targetContext, setTargetContext] = useState<PortalContext | null>(null);
  const [userId, setUserId] = useState("");
  const [brandKey, setBrandKey] = useState("breero");
  const [assignments, setAssignments] = useState<AccessAssignmentInput[]>([{ ...initialAssignment }]);
  const [state, setState] = useState<OperationState>("loading");
  const [message, setMessage] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [loadVersion, setLoadVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    setMessage("");

    Promise.all([
      loadPortalContext(controller.signal),
      customerApi.auth.accessCatalog(controller.signal),
    ])
      .then(([portal, accessCatalog]) => {
        if (!portal.permissions.includes("*") && !portal.permissions.includes("admin.access.manage")) {
          throw new Error("Your account is not authorized to manage access.");
        }
        setOperatorContext(portal);
        setCatalog(accessCatalog);
        setState("idle");
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        const authorizationMessage = reason instanceof Error && reason.message.startsWith("Your account")
          ? reason.message
          : safeCustomerError(reason).message;
        setMessage(authorizationMessage);
        setState("error");
      });

    return () => controller.abort();
  }, [loadVersion]);

  function updateAssignment(index: number, patch: Partial<AccessAssignmentInput>) {
    setAssignments((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, ...patch } : item
    )));
    setMessage("");
    if (state === "success" || state === "error") setState("idle");
  }

  function choosePrimary(index: number, checked: boolean) {
    setAssignments((current) => current.map((item, itemIndex) => ({
      ...item,
      is_primary: checked ? itemIndex === index : itemIndex === index ? false : item.is_primary,
    })));
    setMessage("");
  }

  function changeUserId(value: string) {
    const nextUserId = value.trim();
    setUserId(nextUserId);
    if (targetContext?.user.id !== nextUserId) {
      setTargetContext(null);
      setBrandKey("breero");
    }
    setMessage("");
    if (state === "success" || state === "error") setState("idle");
  }

  async function loadExistingAccess() {
    setMessage("");
    if (!isValidUserId(userId)) {
      setMessage("Enter a valid BREERO user UUID before loading access.");
      setState("error");
      return;
    }

    setState("loading-profile");
    try {
      const result = await customerApi.auth.userAccess(userId);
      const currentAssignments = assignmentsFromContext(result);
      setTargetContext(result);
      setBrandKey(result.brand_key);
      setAssignments(currentAssignments.length ? currentAssignments : [{ ...initialAssignment }]);
      setMessage(
        currentAssignments.length
          ? `Loaded ${currentAssignments.length} assignment${currentAssignments.length === 1 ? "" : "s"} for ${result.user.email}.`
          : `${result.user.email} has no assignments. Add the first assignment before saving.`,
      );
      setState("idle");
    } catch (reason: unknown) {
      setTargetContext(null);
      setMessage(safeCustomerError(reason).message);
      setState("error");
    }
  }

  function prepareReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");

    if (!targetContext || targetContext.user.id !== userId) {
      setMessage("Load the current access profile before replacing assignments.");
      setState("error");
      return;
    }

    const validationErrors = validateAccessAssignments(userId, assignments);
    if (validationErrors.length) {
      setMessage(validationErrors.join(" "));
      setState("error");
      return;
    }

    setState("idle");
    setReviewOpen(true);
  }

  async function confirmSave() {
    if (!targetContext || targetContext.user.id !== userId) return;
    setState("saving");
    setMessage("");

    try {
      const result = await customerApi.auth.replaceUserAccess(userId, {
        brand_key: brandKey,
        assignments,
      });
      setTargetContext(result);
      setAssignments(assignmentsFromContext(result));
      setReviewOpen(false);
      setMessage(`Access updated for ${result.user.email}. Primary dashboard: ${result.dashboard_path}`);
      setState("success");
    } catch (reason: unknown) {
      setReviewOpen(false);
      setMessage(safeCustomerError(reason).message);
      setState("error");
    }
  }

  function resetForm() {
    setUserId("");
    setBrandKey("breero");
    setTargetContext(null);
    setAssignments([{ ...initialAssignment }]);
    setMessage("");
    setReviewOpen(false);
    setState("idle");
  }

  if (state === "loading") {
    return <LoadingState label="Loading access controls" />;
  }
  if (!catalog || !operatorContext) {
    return (
      <ErrorState
        title="Access controls are unavailable"
        description={message || "The role and department catalog could not be loaded."}
        onRetry={() => setLoadVersion((current) => current + 1)}
      />
    );
  }

  const profileLoaded = targetContext?.user.id === userId;

  return (
    <Card id="access-assignment">
      <div className="section-heading">
        <div>
          <p className="market-eyebrow">Authorization administration</p>
          <h2>Department access</h2>
        </div>
        <Badge variant={profileLoaded ? "success" : "neutral"}>
          {profileLoaded ? "Profile loaded" : "Lookup required"}
        </Badge>
      </div>
      <p>
        Review and replace a user’s BREERO role and department assignments. Credentials remain owned by the configured identity provider.
      </p>

      <form onSubmit={prepareReview} noValidate>
        <div className={styles.accessLookup}>
          <FormField
            label="User UUID"
            htmlFor="access-user-id"
            required
            hint="Use the BREERO user ID, not the Keycloak subject. Existing access must be loaded before replacement."
          >
            <SearchInput
              id="access-user-id"
              value={userId}
              onChange={(event) => changeUserId(event.target.value)}
              onClear={resetForm}
              placeholder="123e4567-e89b-42d3-a456-426614174000"
              autoComplete="off"
              required
            />
          </FormField>
          <Button
            type="button"
            variant="outline"
            loading={state === "loading-profile"}
            onClick={loadExistingAccess}
          >
            Load existing access
          </Button>
        </div>

        {targetContext && (
          <Card className={styles.targetSummary} aria-live="polite">
            <h3>Selected user</h3>
            <dl>
              <dt>Name</dt><dd>{targetContext.user.full_name}</dd>
              <dt>Email</dt><dd>{targetContext.user.email}</dd>
              <dt>Identity</dt><dd>{targetContext.identity_mode === "keycloak" ? "Keycloak SSO" : "Local development identity"}</dd>
              <dt>Current dashboard</dt><dd><code>{targetContext.dashboard_path}</code></dd>
              <dt>Brand</dt><dd>{targetContext.brand_key}</dd>
            </dl>
          </Card>
        )}

        <div className={styles.assignmentList} aria-label="Access assignments">
          {assignments.map((assignment, index) => (
            <Card className={styles.assignmentCard} key={`${index}-${assignment.role}-${assignment.department}`}>
              <div className={styles.assignmentHeading}>
                <h3>Assignment {index + 1}</h3>
                <Badge variant={assignment.is_primary ? "brand" : "neutral"}>
                  {assignment.is_primary ? "Primary" : "Additional"}
                </Badge>
              </div>

              <FormField label="Role" htmlFor={`role-${index}`} required>
                <Select
                  id={`role-${index}`}
                  value={assignment.role}
                  onChange={(event) => updateAssignment(index, { role: event.target.value as AccessRole })}
                >
                  {catalog.roles.map((role) => <option value={role} key={role}>{label(role)}</option>)}
                </Select>
              </FormField>

              <FormField label="Department" htmlFor={`department-${index}`} required>
                <Select
                  id={`department-${index}`}
                  value={assignment.department}
                  onChange={(event) => updateAssignment(index, { department: event.target.value as Department })}
                >
                  {catalog.departments.map((item) => <option value={item} key={item}>{label(item)}</option>)}
                </Select>
              </FormField>

              <FormField label="Tenant scope" htmlFor={`scope-${index}`} required>
                <Select
                  id={`scope-${index}`}
                  value={assignment.tenant_scope}
                  onChange={(event) => {
                    const tenantScope = event.target.value as TenantScope;
                    updateAssignment(index, {
                      tenant_scope: tenantScope,
                      vendor_id: tenantScope === "vendor" ? assignment.vendor_id : null,
                    });
                  }}
                >
                  {catalog.tenant_scopes.map((scope) => <option value={scope} key={scope}>{label(scope)}</option>)}
                </Select>
              </FormField>

              {assignment.tenant_scope === "vendor" && (
                <FormField
                  label="Vendor UUID"
                  htmlFor={`vendor-${index}`}
                  required
                  hint="Vendor-scoped roles are restricted to this provider organization."
                >
                  <Input
                    id={`vendor-${index}`}
                    value={assignment.vendor_id ?? ""}
                    onChange={(event) => updateAssignment(index, { vendor_id: event.target.value.trim() || null })}
                    required
                  />
                </FormField>
              )}

              <Checkbox
                label="Primary workspace"
                description="Successful login routes the user to this assignment’s department dashboard."
                checked={assignment.is_primary ?? false}
                onChange={(event) => choosePrimary(index, event.target.checked)}
              />
              <Button
                type="button"
                variant="ghost"
                onClick={() => setAssignments((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                disabled={assignments.length === 1}
              >
                Remove assignment
              </Button>
            </Card>
          ))}
        </div>

        <div className="actions">
          <Button
            type="button"
            variant="outline"
            onClick={() => setAssignments((current) => [...current, { ...initialAssignment, is_primary: false }])}
          >
            Add assignment
          </Button>
          <Button type="button" variant="ghost" onClick={resetForm}>Reset form</Button>
          <Button type="submit" disabled={!profileLoaded || state === "saving"}>Review access changes</Button>
        </div>

        {message && (
          <p
            className={styles.statusMessage}
            role={state === "error" ? "alert" : "status"}
            aria-live="polite"
          >
            {message}
          </p>
        )}
      </form>

      <Drawer
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        title="Review access replacement"
        description={targetContext ? `Confirm the complete assignment set for ${targetContext.user.email}.` : undefined}
        footer={(
          <div className={styles.drawerFooter}>
            <Button variant="outline" onClick={() => setReviewOpen(false)} disabled={state === "saving"}>Cancel</Button>
            <Button onClick={confirmSave} loading={state === "saving"}>Confirm access changes</Button>
          </div>
        )}
      >
        <p>This operation replaces the user’s complete BREERO access profile for the <strong>{brandKey}</strong> brand. It does not change identity-provider credentials.</p>
        <ul className={styles.reviewList}>
          {assignments.map((assignment, index) => (
            <li key={`${assignment.role}-${assignment.department}-${index}`}>
              <strong>Assignment {index + 1}</strong>
              <p>{assignmentLabel(assignment)}</p>
            </li>
          ))}
        </ul>
      </Drawer>
    </Card>
  );
}
