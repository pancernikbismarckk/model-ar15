using System;
using System.IO;
using System.Linq;
using System.Xml;
using CodeWalker.GameFiles;

// cwconv xml2bin <in.{ydr,ytd,ycd,ytyp}.xml> <out_dir> -> writes <name>.ydr / .ytd / .ycd / .ytyp
// cwconv check <file.{ydr,ytd,ycd,ytyp}>               -> loads the binary and prints a summary
// cwconv bin2xml <file.{ydr,ytd,ycd}> <out_dir>        -> CodeWalker XML (+ DDS textures in <out_dir>/<name>/)
static class Program
{
    static int Main(string[] args)
    {
        if (args.Length < 2) { Console.Error.WriteLine("usage: cwconv xml2bin <in.xml> <out_dir> | check <file>"); return 2; }
        try
        {
            if (args[0] == "xml2bin") return Xml2Bin(args[1], args[2]);
            if (args[0] == "check") return Check(args[1]);
            if (args[0] == "bin2xml") return Bin2Xml(args[1], args[2]);
        }
        catch (Exception e) { Console.Error.WriteLine("error: " + e); return 1; }
        return 2;
    }

    static int Xml2Bin(string inPath, string outDir)
    {
        string xml = File.ReadAllText(inPath);
        string folder = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(inPath)), Path.GetFileName(inPath).Split('.')[0]);
        string name = Path.GetFileName(inPath);
        Directory.CreateDirectory(outDir);
        byte[] data;
        string outName;
        if (name.EndsWith(".ydr.xml"))
        {
            var ydr = XmlYdr.GetYdr(xml, folder);
            data = ydr.Save();
            outName = name.Substring(0, name.Length - 4);
        }
        else if (name.EndsWith(".ytd.xml"))
        {
            var ytd = XmlYtd.GetYtd(xml, folder);
            data = ytd.Save();
            outName = name.Substring(0, name.Length - 4);
        }
        else if (name.EndsWith(".ycd.xml"))
        {
            data = XmlYcd.GetYcd(xml).Save();
            outName = name.Substring(0, name.Length - 4);
        }
        else if (name.EndsWith(".ytyp.xml"))
        {
            var doc = new XmlDocument();
            doc.LoadXml(xml);
            data = XmlMeta.GetRSCData(doc) ?? throw new Exception("empty ytyp");
            outName = name.Substring(0, name.Length - 4);
        }
        else throw new Exception("unsupported file " + name);
        string outPath = Path.Combine(outDir, outName);
        File.WriteAllBytes(outPath, data);
        Console.WriteLine($"{outPath}: {data.Length} bytes");
        return 0;
    }

    static int Bin2Xml(string path, string outDir)
    {
        byte[] data = File.ReadAllBytes(path);
        string name = Path.GetFileName(path);
        string folder = Path.Combine(outDir, Path.GetFileNameWithoutExtension(path));
        Directory.CreateDirectory(folder);
        string xml;
        if (path.EndsWith(".ydr")) { var ydr = new YdrFile(); ydr.Load(data); xml = YdrXml.GetXml(ydr, folder); }
        else if (path.EndsWith(".ytd")) { var ytd = new YtdFile(); ytd.Load(data); xml = YtdXml.GetXml(ytd, folder); }
        else if (path.EndsWith(".ycd")) { var ycd = new YcdFile(); RpfFile.LoadResourceFile(ycd, data, 46); xml = YcdXml.GetXml(ycd); }
        else throw new Exception("unsupported file " + name);
        File.WriteAllText(Path.Combine(outDir, name + ".xml"), xml);
        Console.WriteLine(Path.Combine(outDir, name + ".xml"));
        return 0;
    }

    static int Check(string path)
    {
        byte[] data = File.ReadAllBytes(path);
        if (path.EndsWith(".ydr"))
        {
            var ydr = new YdrFile();
            ydr.Load(data);
            var d = ydr.Drawable;
            Console.WriteLine($"{Path.GetFileName(path)}: drawable '{d.Name}'");
            var sk = d.Skeleton;
            if (sk != null)
                Console.WriteLine("  bones: " + string.Join(", ", sk.Bones.Items.Select(b => $"{b.Name}#{b.Tag}")));
            var models = d.DrawableModels?.High ?? new DrawableModel[0];
            int tris = 0, verts = 0;
            foreach (var m in models)
                foreach (var g in m.Geometries)
                {
                    tris += (int)g.IndicesCount / 3; verts += g.VerticesCount;
                    Console.WriteLine($"  model skinned={m.SkeletonBinding}, geom shader#{g.ShaderID} verts={g.VerticesCount} tris={g.IndicesCount / 3} layout={g.VertexBuffer?.Info?.Types}/{g.VertexBuffer?.Info?.Flags:X}");
                }
            Console.WriteLine($"  total verts={verts} tris={tris}");
            foreach (var s in d.ShaderGroup.Shaders.data_items)
                Console.WriteLine($"  shader {s.Name} ({s.FileName}) params={s.ParametersList?.Count}");
            var txd = d.ShaderGroup.TextureDictionary;
            if (txd != null) Console.WriteLine("  embedded textures: " + string.Join(", ", txd.Textures.data_items.Select(t => $"{t.Name} {t.Width}x{t.Height} {t.Format} mips={t.Levels}")));
        }
        else if (path.EndsWith(".ytd"))
        {
            var ytd = new YtdFile();
            ytd.Load(data);
            Console.WriteLine($"{Path.GetFileName(path)}: " + string.Join(", ", ytd.TextureDict.Textures.data_items.Select(t => $"{t.Name} {t.Width}x{t.Height} {t.Format} mips={t.Levels}")));
        }
        else if (path.EndsWith(".ycd"))
        {
            var ycd = new YcdFile();
            RpfFile.LoadResourceFile(ycd, data, 46);
            Console.WriteLine($"{Path.GetFileName(path)}: {ycd.ClipMapEntries?.Length ?? 0} clips, {ycd.AnimMapEntries?.Length ?? 0} animations");
            foreach (var c in ycd.ClipMapEntries ?? new ClipMapEntry[0])
            {
                var clip = c.Clip;
                string anim = "";
                if (clip is ClipAnimation ca && ca.Animation != null)
                {
                    var a = ca.Animation;
                    var bones = a.BoneIds?.data_items ?? new AnimationBoneId[0];
                    anim = $" -> {a.Frames} frames {a.Duration:0.###}s, {bones.Length} tracks (bones {bones.Select(b => b.BoneId).Distinct().Count()})"
                         + $", {ca.StartTime:0.###}-{ca.EndTime:0.###}s rate {ca.Rate}";
                }
                Console.WriteLine($"  clip '{clip?.ShortName ?? clip?.Name}'{anim}");
            }
        }
        else if (path.EndsWith(".ytyp"))
        {
            var ytyp = new YtypFile();
            ytyp.Load(data);
            Console.WriteLine($"{Path.GetFileName(path)}: " + string.Join(", ", (ytyp.AllArchetypes ?? new Archetype[0]).Select(a => $"{a.Name} (lod {a._BaseArchetypeDef.lodDist}, flags {a._BaseArchetypeDef.flags}, txd {a._BaseArchetypeDef.textureDictionary})")));
        }
        return 0;
    }
}
