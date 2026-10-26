import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';

const loadDependency = createRequire(import.meta.url);
const compile = path => ts.transpileModule(fs.readFileSync(path, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const reserved = { exports: {} };
new Function('module', 'exports', compile('src/lib/reserved-time.ts'))(reserved, reserved.exports);
const componentCode = compile('src/components/client-schedule-week.tsx');

// Exercise the component's event handlers and state transitions without a DOM.
// Native browser drag initiation still requires a browser interaction check.
function mount(busyTimes = []) {
  const state = [];
  let cursor = 0;
  const hooks = {
    useState(initial) {
      const index = cursor++;
      if (!(index in state)) state[index] = typeof initial === 'function' ? initial() : initial;
      return [state[index], next => { state[index] = typeof next === 'function' ? next(state[index]) : next; }];
    },
    useMemo: calculate => calculate(),
  };
  const component = { exports: {} };
  new Function('module', 'exports', 'require', componentCode)(component, component.exports, name => {
    if (name === 'react') return hooks;
    if (name === '@/lib/reserved-time') return reserved.exports;
    return loadDependency(name);
  });
  const monday = new Date();
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  const at = minute => {
    const date = new Date(monday);
    date.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
    return date.toISOString();
  };
  const appointment = { id: 'session', status: 'scheduled', starts_at: at(11 * 60), ends_at: at(11 * 60 + 50), appointment_type: 'recurring' };
  const moves = [];
  const props = { appointments: [appointment], busyTimes: busyTimes.map(([start, end]) => ({ starts_at: at(start), ends_at: at(end) })), busy: false, durationMinutes: 50, onReschedule: async (...args) => { moves.push(args); }, onCreate: async () => {}, onCancel: async () => {} };
  const render = () => { cursor = 0; return component.exports.ClientScheduleWeek(props); };
  return { render, moves, appointment, at };
}

function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree?.props) return [];
  return [tree, ...nodes(tree.props.children)];
}

function dragEvent(minute) {
  return {
    currentTarget: { getBoundingClientRect: () => ({ top: 100 }) },
    clientY: 100 + (minute - 9 * 60) / 30 * 34 + 0.1,
    dataTransfer: { setData() {} },
    prevented: false,
    preventDefault() { this.prevented = true; },
  };
}

test('day-column drag previews snap to ten minutes and dropping stages confirmation', () => {
  const view = mount();
  let tree = nodes(view.render());
  tree.find(node => node.type === 'article').props.onDragStart(dragEvent(11 * 60));
  for (const minute of [600, 610, 620]) {
    tree = nodes(view.render());
    const source = tree.find(node => node.type === 'article');
    assert.equal(source.props.draggable, true);
    assert.ok(!source.props.className.includes('pointer-events-none'));
    const event = dragEvent(minute);
    tree.find(node => node.props.onDrop).props.onDragOver(event);
    assert.equal(event.prevented, true);
    assert.equal(event.dataTransfer.dropEffect, 'move');
    const preview = nodes(view.render()).find(node => node.props['aria-hidden'] === 'true' && node.props.className?.includes('border-2'));
    assert.ok(preview.props.className.includes('pointer-events-none'));
    assert.equal(preview.props.style.top, `${(minute - 540) / 30 * 34}px`);
    assert.equal(preview.props.style.height, `${50 / 30 * 34}px`);
  }
  nodes(view.render()).find(node => node.props.onDrop).props.onDrop(dragEvent(620));
  tree = nodes(view.render());
  assert.ok(tree.some(node => node.props.role === 'dialog'));
  assert.equal(view.moves.length, 0);
  tree.find(node => node.type === 'button' && node.props.autoFocus).props.onClick();
  assert.equal(view.moves.length, 1);
  assert.equal(view.moves[0][0].id, view.appointment.id);
  assert.equal(view.moves[0][1].toISOString(), view.at(620));
});

test('reserved times reject hovering and dropping without opening confirmation', () => {
  const view = mount([[570, 620]]);
  nodes(view.render()).find(node => node.type === 'article').props.onDragStart(dragEvent(660));
  const day = nodes(view.render()).find(node => node.props.onDrop);
  const event = dragEvent(580);
  day.props.onDragOver(event);
  assert.equal(event.prevented, false);
  assert.equal(event.dataTransfer.dropEffect, 'none');
  day.props.onDrop(event);
  assert.ok(!nodes(view.render()).some(node => node.props.role === 'dialog'));
  assert.equal(view.moves.length, 0);
});
