locale_key = "ja_JP"

translation_dictionary = {
    (
        "*",
        "The installed VRM add-on is not compatible with Blender {blender_version}. "
        + "Please upgrade the add-on.",
    ): "インストールされているVRMアドオンはBlender {blender_version}には未対応です。\nアドオンをバージョンアップしてください。",
    (
        "*",
        "The installed VRM add-on is\nnot compatible with Blender {blender_version}.\n"
        + "Please upgrade the add-on.",
    ): "インストールされている\nVRMアドオンはBlender {blender_version}には\n未対応です。アドオンを\nバージョンアップしてください。",
    (
        "*",
        "The installed VRM add-on is not compatible with Blender {blender_version}. "
        + " The VRM may not be exported correctly.",
    ): "インストールされているVRMアドオンはBlender {blender_version}には未対応です。VRMが正しくエクスポートされない可能性があります。",
    ("*", 'Set shading type to "Material"'): "3Dビューをマテリアルプレビューに設定",
    ("*", 'Set view transform to "Standard"'): "ビュー変換を「標準」に設定",
    (
        "*",
        'Set an imported armature display to "Wire"',
    ): "アーマチュアのビューポート表示を「ワイヤーフレーム」に設定",
    ("*", 'Set an imported armature display to show "In-Front"'): "アーマチュアを最前面に表示",
    ("*", "Export Invisible Objects"): "非表示のオブジェクトも含める",
    ("*", "Export Only Selections"): "選択されたオブジェクトのみ",
    ("*", "Enable Advanced Options"): "高度なオプションを有効にする",
    (
        "*",
        "Try the FB_ngon_encoding under development (Exported meshes can be corrupted)",
    ): "開発中のFB_ngon_encodingエクステンションを試してみる(エクスポートされるメッシュが壊れることがあります)",
    (
        "*",
        "VRM 1.0 support is under development.\n"
        + "It won't work as intended in many situations.",
    ): "VRM 1.0対応機能は現在開発中です。\n"
    + "多くの状況で意図通り動作しません。\n",
    ("*", "No error. Ready for export VRM"): "エラーはありませんでした。VRMのエクスポートをすることができます",
    (
        "*",
        "No error. But there're {warning_count} warning(s)."
        + " The output may not be what you expected.",
    ): "エラーはありませんでしたが、{warning_count}件の警告があります。期待通りの出力にはならないかもしれません。",
    ("*", "VRM Export"): "VRMエクスポート",
    ("*", "Create VRM Model"): "VRMモデルを作成",
    ("*", "Validate VRM Model"): "VRMモデルのチェック",
    ("*", "Extract texture images into the folder"): "テクスチャ画像をフォルダに展開",
    (
        "*",
        'Official add-on "glTF 2.0 format" is required. Please enable it.',
    ): "公式アドオン「glTF 2.0 format」が必要です。有効化してください。",
    ("*", "For more information please check following URL."): "詳しくは下記のURLを確認してください。",
    ("*", "Import Anyway"): "インポートします",
    ("*", "A light is required"): "ライトが必要です",
    ("*", "License Confirmation"): "ライセンスの確認",
    (
        "*",
        'Is this VRM allowed to edited? Please check its "{json_key}" value.',
    ): "指定されたVRMのメタデータ「{json_key}」には独自のライセンスのURLが設定されています。",
    (
        "*",
        'This VRM is licensed by VRoid Hub License "Alterations: No".',
    ): "指定されたVRMにはVRoid Hubの「改変: NG」ライセンスが設定されています。",
    (
        "*",
        'This VRM is licensed by UV License with "Remarks".',
    ): "指定されたVRMには特記事項(Remarks)付きのUVライセンスが設定されています。",
    (
        "*",
        'The VRM selects "Other" license but no license url is found.',
    ): "指定されたVRMには「Other」ライセンスが設定されていますが、URLが設定されていません。",
    (
        "*",
        'The VRM is licensed by "{license_name}". No derivative works are allowed.',
    ): "指定されたVRMには改変不可ライセンス「{license_name}」が設定されています。改変することはできません。",
    (
        "*",
        "The FB_ngon_encoding extension under development will be used. "
        + "The exported mesh may be corrupted.",
    ): "開発中のFB_ngon_encodingエクステンションが有効です。エクスポートされるメッシュが壊れることがあります。",
    (
        "*",
        "Nodes(mesh,bones) require unique names for VRM export. {name} is duplicated.",
    ): "glTFノード要素(メッシュ、ボーン)の名前は重複してはいけません。「{name}」が重複しています。",
    ("*", 'There are not an object on the origin "{name}"'): "「{name}」が原点座標にありません",
    (
        "*",
        "The same name cannot be used for a mesh object and a bone. "
        + 'Rename either one whose name is "{name}".',
    ): "メッシュオブジェクトとボーンで同じ名前を使うことができません。"
    + "名前が「{name}」のどちらかの名前を変更してください。",
    (
        "*",
        'The "{name}" mesh has both a non-armature modifier and a shape key. '
        + "However, they cannot coexist, so shape keys may not be export correctly.",
    ): "メッシュ「{name}」にアーマチュア以外のモディファイアとシェイプキーが両方設定されていますが、"
    + "それらは共存できないためシェイプキーが正しく出力されないことがあります。",
    (
        "*",
        'Spring "{spring_name1}" and "{spring_name2}" have'
        + ' common bone "{bone_name}".',
    ): "Spring 「{spring_name1}」と「{spring_name2}」が「{bone_name}」ボーンを共有しています。",
    (
        "*",
        "Only one armature is required for VRM export. Multiple armatures found.",
    ): "VRM出力の際、選択できるアーマチュアは1つのみです。複数選択されています。",
    (
        "*",
        "VRM Required Bones",
    ): "VRM必須ボーン",
    (
        "*",
        "VRM Optional Bones",
    ): "VRMオプションボーン",
    (
        "*",
        'Required VRM Bone "{humanoid_name}" is not assigned. Please confirm'
        + ' "VRM" Panel → "VRM 0.x Humanoid" → "VRM Required Bones" → "{humanoid_name}".',
    ): "VRM必須ボーン「{humanoid_name}」が未割り当てです。"
    + "「VRM」パネルの「VRM 0.x Humanoid」→「VRM必須ボーン」で「{humanoid_name}」ボーンの設定をしてください。",
    (
        "*",
        'Couldn\'t assign the "{bone}" bone to a VRM "{human_bone}". '
        + 'Please confirm "VRM" Panel → "VRM 0.x Humanoid" → {human_bone}.',
    ): "ボーン「{bone}」をVRMボーン「{human_bone}」に割り当てることができませんでした。"
    + "「VRM」パネルの「VRM 0.x Humanoid」で「{human_bone}」ボーンの設定を確認してください。",
    (
        "*",
        'Required VRM Bone "{humanoid_name}" is not assigned. Please confirm'
        + ' "VRM" Panel → "Humanoid" → "VRM Required Bones" → "{humanoid_name}".',
    ): "VRM必須ボーン「{humanoid_name}」が未割り当てです。"
    + "「VRM」パネルの「Humanoid」→「VRM必須ボーン」で「{humanoid_name}」ボーンの設定をしてください。",
    (
        "*",
        'Couldn\'t assign the "{bone}" bone to a VRM "{human_bone}". '
        + 'Please confirm "VRM" Panel → "Humanoid" → {human_bone}.',
    ): "ボーン「{bone}」をVRMボーン「{human_bone}」に割り当てることができませんでした。"
    + "「VRM」パネルの「Humanoid」で「{human_bone}」ボーンの設定を確認してください。",
    (
        "*",
        'Please assign Required VRM Bone "{name}".',
    ): "VRM必須ボーン「{name}」を割り当ててください。",
    (
        "*",
        'Please assign "{parent_name}" because "{name}" requires it as its child bone.',
    ): "「{parent_name}」を割り当ててください。子ボーンである「{name}」の割り当てに必要になります。",
    (
        "*",
        'Faces must be Triangle, but not face in "{name}" or '
        + "it will be triangulated automatically.",
    ): "「{name}」のポリゴンに三角形以外のものが含まれます。自動的に三角形に分割されます。",
    (
        "*",
        'VRM Bone "{child}" needs "{parent}". Please confirm'
        + ' "VRM" Panel → "Humanoid" → "VRM Optional Bones" → "{parent}".',
    ): "VRMボーン「{child}」は「{parent}」が必要です。"
    + "「VRM」パネルの「Humanoid」→「VRMオプションボーン」で「{parent}」ボーンの設定をしてください。",
    (
        "*",
        'Object "{name}" contains a negative value for the scale;'
        + " VRM 1.0 does not allow negative values to be specified for the scale.",
    ): "オブジェクト「{name}」にスケールにマイナス値が含まれています。VRM 1.0ではスケールにマイナス値を指定できません。",
    (
        "*",
        'Node Constraint "{owner_name} / {constraint_name}" has a circular dependency',
    ): "ノードコンストレイント「{owner_name} / {constraint_name}」に循環依存関係が存在します。",
    ("*", "Please add ARMATURE to selections"): "アーマチュアを選択範囲に含めてください",
    (
        "*",
        'vertex index "{vertex_index}" is no weight in "{mesh_name}". '
        + "Add weight to parent bone automatically.",
    ): "「{mesh_name}」の頂点id「{vertex_index}」にウェイトが乗っていません。"
    + "親ボーンへのウエイトを自動で割り当てます。",
    (
        "*",
        'vertex index "{vertex_index}" has too many(over 4) weight in "{mesh_name}". '
        + "It will be truncated to 4 descending order by its weight.",
    ): "「{mesh_name}」の頂点id「{vertex_index}」に影響を与えるボーンが5以上あります。"
    + "重い順に4つまでエクスポートされます。",
    (
        "*",
        '"{material_name}" needs to enable "VRM MToon Material" or'
        + " connect Principled BSDF/MToon_unversioned/TRANSPARENT_ZWRITE"
        + ' to "Surface" directly. Empty material will be exported.',
    ): "マテリアル「{material_name}」は「VRM MToon Material」を有効にするか"
    + "「プリンシプルBSDF」「MToon_unversioned」「TRANSPARENT_ZWRITE」の"
    + "いずれかを直接「サーフェス」に指定してください。空のマテリアルを出力します。",
    (
        "*",
        '"{image_name}" is not found in file path "{image_filepath}". '
        + "Please load file of it in Blender.",
    ): '「{image_name}」の画像ファイルが指定ファイルパス「"{image_filepath}"」'
    + "に存在しません。画像を読み込み直してください。",
    (
        "*",
        "firstPersonBone is not found. "
        + 'Set VRM HumanBone "head" instead automatically.',
    ): "firstPersonBoneが設定されていません。"
    + "代わりにfirstPersonBoneとしてVRMヒューマンボーン「head」を自動で設定します。",
    (
        "*",
        'mesh "{mesh_name}" doesn\'t have shape key. '
        + 'But blend shape group needs "{shape_key_name}" in its shape key.',
    ): "blend shape groupが参照しているメッシュ「{mesh_name}」のシェイプキー「{shape_key_name}」が存在しません。",
    (
        "*",
        'mesh "{mesh_name}" doesn\'t have "{shape_key_name}" shape key. '
        + "But blend shape group needs it.",
    ): "メッシュ「{mesh_name}」にはシェイプキー「{shape_key_name}」が存在しません。"
    + "しかし blend shape group の設定はそれを必要としています。",
    (
        "*",
        'need "{expect_node_type}" input in "{shader_val}" of "{material_name}"',
    ): "「{material_name}」の「{shader_val}」には、「{expect_node_type}」を直接つないでください。 ",
    (
        "*",
        'image in material "{material_name}" is not put. Please set image.',
    ): "マテリアル「{material_name}」にテクスチャが設定されていないimageノードがあります。削除か画像を設定してください。",
    ("*", "Simplify VRoid Bones"): "VRoidのボーン名を短くする",
    ("*", "Current Pose"): "現在のポーズ",
    ("*", "Save Bone Mappings"): "ボーンの対応を保存",
    ("*", "Load Bone Mappings"): "ボーンの対応を読み込み",
    ("*", "All VRM Required Bones have been assigned."): "全てのVRM必須ボーンの割り当てが行われました。",
    (
        "*",
        "There are unassigned VRM Required Bones. Please assign all.",
    ): "未割り当てのVRM必須ボーンが存在します。全てのVRM必須ボーンを割り当ててください。",
    ("Operator", "Automatic Bone Assignment"): "ボーンの自動割り当て",
    ("Operator", "Preview MToon"): "MToonのプレビュー",
    ("Operator", "VRM Humanoid"): "VRMヒューマノイド",
    ("Operator", "VRM License Confirmation"): "VRM利用条件の確認",
    ("Operator", "VRM Required Bones Assignment"): "VRM必須ボーンの設定",
    (
        "*",
        "Conditions exported as Roll Constraint\n"
        + " - Copy Rotation\n"
        + " - Enabled\n"
        + " - No Vertex Group\n"
        + " - Axis is one of X, Y and Z\n"
        + " - No Inverted\n"
        + " - Mix is Add\n"
        + " - Target is Local Space\n"
        + " - Owner is Local Space\n"
        + " - No circular dependencies\n"
        + " - The one at the top of the list of\n"
        + "   those that meet all the conditions\n",
    ): "Roll Constraintになる条件\n"
    + " - 回転コピー\n"
    + " - 有効状態\n"
    + " - 頂点グループの指定無し\n"
    + " - 座標軸はXYZのどれか一つを指定\n"
    + " - 反転は無し\n"
    + " - ミックスは追加\n"
    + " - ターゲットはローカル空間\n"
    + " - オーナーはローカル空間\n"
    + " - 循環依存関係が存在しない\n"
    + " - 複数が条件を満たす場合は一番上にあるもの\n",
    (
        "*",
        "Conditions exported as Aim Constraint\n"
        + " - Damped Track\n"
        + " - Enabled\n"
        + " - Target Bone Head/Tail is 0\n"
        + " - No Follow Target Bone B-Bone\n"
        + " - No circular dependencies\n"
        + " - The one at the top of the list of\n"
        + "   those that meet all the conditions\n",
    ): "Aim Constraintになる条件\n"
    + " - 減衰トラック\n"
    + " - 有効状態\n"
    + " - ターゲットボーンのヘッド/テールが0\n"
    + " - ターゲットボーンのBボーンには従わない\n"
    + " - 循環依存関係が存在しない\n"
    + " - 複数が条件を満たす場合は一番上にあるもの\n",
    (
        "*",
        "Conditions exported as Rotation Constraint\n"
        + " - Copy Rotation\n"
        + " - Enabled\n"
        + " - No Vertex Group\n"
        + " - Axis is X, Y and Z\n"
        + " - No Inverted\n"
        + " - Mix is Add\n"
        + " - Target is Local Space\n"
        + " - Owner is Local Space\n"
        + " - No circular dependencies\n"
        + " - The one at the top of the list of\n"
        + "   those that meet all the conditions\n",
    ): "Rotation Constraintになる条件\n"
    + " - 回転コピー\n"
    + " - 有効状態\n"
    + " - 頂点グループの指定無し\n"
    + " - 座標軸はXYZ全て指定\n"
    + " - 反転は無し\n"
    + " - ミックスは追加\n"
    + " - ターゲットはローカル空間\n"
    + " - オーナーはローカル空間\n"
    + " - 循環依存関係が存在しない\n"
    + " - 複数が条件を満たす場合は一番上にあるもの\n",
    (
        "*",
        "This VRM uses Draco compression. Unable to decompress.",
    ): "Draco圧縮されたVRMは未対応です",
    ("*", "Axis Translation on Export"): "エクスポート時の軸の変換",
    ("*", "Offset and Scale are ignored in VRM 0.0"): "VRM 0.0ではオフセットとスケールは無視されます",
    (
        "*",
        'Material "{name}" {texture}\'s Offset and Scale are ignored in VRM 0.0',
    ): "VRM 0.0ではマテリアル「{name}」の{texture}のオフセットとスケールは無視されます",
    (
        "*",
        "Offset and Scale in VRM 0.0 are the values of the Lit Color Texture",
    ): "VRM 0.0でのオフセットとスケールはLit Colorテクスチャの値になります",
    (
        "*",
        'Material "{name}" {texture}\'s Offset and Scale in VRM 0.0 are the values of '
        + "the Lit Color Texture",
    ): "VRM 0.0でのマテリアル「name」の{texture}のオフセットとスケールはLit Colorテクスチャの値になります",
    (
        "*",
        'It is recommended to set "{colorspace}" to "{input_colorspace}" for "{texture_label}"',
    ): "{texture_label}の{input_colorspace}には「{colorspace}」の設定が推奨されます",
    (
        "*",
        'It is recommended to set "{colorspace}" to "{input_colorspace}" for "{texture_label}"'
        + ' in Material "{name}"',
    ): "マテリアル{name}の{texture_label}の{input_colorspace}には「{colorspace}」の設定が推奨されます。",
    (
        "*",
        "VRM Material",
    ): "VRMマテリアル",
    (
        "*",
        "(Experimental!) Enable VRM MToon Material",
    ): "(実験中の機能です!) VRM MToonマテリアルを有効にする",
    (
        "*",
        "Export Shape Key Normals",
    ): "シェイプキー法線をエクスポートする",
    (
        "*",
        "How to export this material to VRM.\n"
        + "Meet one of the following conditions.\n"
        + " - VRM MToon material is enabled\n"
        + ' - Connect the "Surface" to a "Principled BSDF"\n'
        + ' - Connect the "Surface" to a "MToon_unversioned"\n'
        + ' - Connect the "Surface" to a "TRANSPARENT_ZWRITE"\n'
        + " - Others that are compatible with the glTF 2.0 add-on export\n",
    ): "VRMにこのマテリアルをエクスポートする方法\n"
    + "次のいずれかの条件を満たしてください。\n"
    + " - VRM MToonマテリアルが有効\n"
    + " - 「サーフェス」に「プリンシプルBSDF」を指定\n"
    + " - 「サーフェス」に「MToon_unversioned」を指定\n"
    + " - 「サーフェス」に「TRANSPARENT_ZWRITE」を指定\n"
    + " - その他、glTF 2.0アドオンのエクスポートに対応しているもの\n",
}
